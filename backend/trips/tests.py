from datetime import datetime, timezone
import threading
import time
import urllib.error
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from trips.providers.errors import ProviderError
from trips.providers.geocoding import geocode
from trips.providers.http import ThreadSafeRateLimiter, request_with_retry
from trips.providers.routing import RouteResult, fetch_route_alternatives
from trips.serializers import TripRequestSerializer

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class HealthEndpointTests(SimpleTestCase):
    def test_health_is_database_and_provider_free(self) -> None:
        # SimpleTestCase rejects database access. Patching urlopen additionally
        # makes an accidental provider call fail this test.
        with patch("urllib.request.urlopen") as urlopen:
            response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})
        urlopen.assert_not_called()

    def test_health_is_not_subject_to_api_throttling(self) -> None:
        for _ in range(12):
            response = self.client.get(reverse("health"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class TripsRootEndpointTests(APITestCase):
    def test_post_requires_all_fields(self) -> None:
        response = self.client.post(
            reverse("trips:root"), {"start": "Chicago, IL"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.json()
        self.assertIn("end", body)
        self.assertIn("load_lb", body)
        self.assertIn("depart_at", body)
        self.assertIn("sample_miles", body)

    def test_post_rejects_non_positive_load(self) -> None:
        response = self.client.post(
            reverse("trips:root"),
            {
                "start": "A",
                "end": "B",
                "load_lb": 0,
                "depart_at": "2026-10-15T18:00:00Z",
                "sample_miles": 25,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("load_lb", response.json())

    def test_post_rejects_an_unsupported_spacing(self) -> None:
        response = self.client.post(
            reverse("trips:root"),
            {
                "start": "A",
                "end": "B",
                "load_lb": 40000,
                "depart_at": "2026-10-15T18:00:00Z",
                "sample_miles": 15,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sample_miles", response.json())


class TripRequestSerializerTests(SimpleTestCase):
    def payload(self, **overrides):
        data = {
            "start": "Pune",
            "end": "Delhi",
            "load_lb": 40_000,
            "depart_at": datetime(2026, 10, 21, 8, tzinfo=timezone.utc).isoformat(),
            "sample_miles": 25,
        }
        data.update(overrides)
        return data

    def test_accepts_timezone_aware_departure(self):
        serializer = TripRequestSerializer(data=self.payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_non_positive_load(self):
        serializer = TripRequestSerializer(data=self.payload(load_lb=0))
        self.assertFalse(serializer.is_valid())
        self.assertIn("load_lb", serializer.errors)

    def test_rejects_empty_place_name(self):
        serializer = TripRequestSerializer(data=self.payload(start="  "))
        self.assertFalse(serializer.is_valid())
        self.assertIn("start", serializer.errors)


class ProviderRetryTests(SimpleTestCase):
    @patch("trips.providers.http.time.sleep")
    def test_retries_once_after_transient_failure(self, sleep):
        attempts = 0

        def operation():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise urllib.error.URLError("temporary")
            return "ok"

        self.assertEqual(request_with_retry(operation, service_name="Weather service"), "ok")
        self.assertEqual(attempts, 2)
        sleep.assert_called_once_with(0.25)

    def test_geocoding_rate_limits_every_retry_attempt(self):
        cache.clear()
        response = MagicMock()
        response.read.return_value = (
            b'[{"display_name":"Pune, India","lat":"18.5204","lon":"73.8567"}]'
        )
        response.__enter__.return_value = response

        with (
            patch(
                "trips.providers.geocoding.urllib.request.urlopen",
                side_effect=[urllib.error.URLError("temporary"), response],
            ) as urlopen,
            patch(
                "trips.providers.geocoding.NOMINATIM_RATE_LIMITER.run",
                side_effect=lambda operation: operation(),
            ) as rate_limited_run,
            patch("trips.providers.http.time.sleep"),
        ):
            result = geocode("retry-rate-limit-test-pune")

        self.assertEqual(result.label, "Pune, India")
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(rate_limited_run.call_count, 2)


class ProviderRateLimiterConcurrencyTests(SimpleTestCase):
    def test_concurrent_threads_receive_spaced_attempt_slots(self):
        interval = 0.02
        limiter = ThreadSafeRateLimiter(interval)
        barrier = threading.Barrier(4)
        starts: list[float] = []
        errors: list[BaseException] = []
        results_lock = threading.Lock()

        def wait_for_slot() -> None:
            try:
                barrier.wait()
                started = limiter.run(time.monotonic)
                with results_lock:
                    starts.append(started)
            except BaseException as exc:  # pragma: no cover - surfaced below
                with results_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=wait_for_slot) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        self.assertFalse(errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        ordered = sorted(starts)
        self.assertEqual(len(ordered), 4)
        for earlier, later in zip(ordered, ordered[1:]):
            self.assertGreaterEqual(later - earlier, interval * 0.9)


class LongRouteTests(SimpleTestCase):
    def test_retries_a_provider_distance_limit_as_two_stitched_legs(self):
        first_leg = RouteResult([[73.0, 18.0], [75.0, 20.0]], 400, 10)
        second_leg = RouteResult([[75.0, 20.0], [77.0, 22.0]], 500, 12)
        with (
            patch(
                "trips.providers.routing._request_route",
                side_effect=[{"error": "maximum route distance 1500000 meters"}, {}, {}],
            ) as request_route,
            patch(
                "trips.providers.routing.routes_from_payload",
                side_effect=[
                    ProviderError("maximum route distance 1500000 meters"),
                    [first_leg],
                    [second_leg],
                ],
            ),
        ):
            routes = fetch_route_alternatives(18.5, 73.8, 22.7, 77.1)

        self.assertEqual(request_route.call_count, 3)
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].coords, [[73.0, 18.0], [75.0, 20.0], [77.0, 22.0]])
        self.assertEqual(routes[0].distance_mi, 900)
        self.assertEqual(routes[0].duration_hr, 22)
        self.assertEqual(routes[0].segment_count, 2)

    @patch("trips.providers.http.time.sleep")
    def test_returns_clear_error_after_retries_are_exhausted(self, sleep):
        with self.assertRaisesRegex(ProviderError, "temporarily unavailable"):
            request_with_retry(
                lambda: (_ for _ in ()).throw(urllib.error.URLError("offline")),
                service_name="Weather service",
            )
        sleep.assert_called_once_with(0.25)
