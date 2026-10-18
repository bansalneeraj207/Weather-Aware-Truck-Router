from datetime import datetime, timezone
import urllib.error
from unittest.mock import patch

from django.test import SimpleTestCase

from trips.providers.errors import ProviderError
from trips.providers.http import request_with_retry
from trips.providers.routing import RouteResult, fetch_route_alternatives
from trips.serializers import TripRequestSerializer

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


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
