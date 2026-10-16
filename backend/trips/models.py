from django.db import models


class Trip(models.Model):
    """A driver's planning request and the resolved endpoints."""

    start_label = models.CharField(max_length=200)
    start_lat = models.FloatField()
    start_lon = models.FloatField()

    end_label = models.CharField(max_length=200)
    end_lat = models.FloatField()
    end_lon = models.FloatField()

    load_lb = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.start_label} -> {self.end_label} ({self.load_lb} lb)"


class RouteOption(models.Model):
    """One route alternative for a trip, with its computed risk result."""

    trip = models.ForeignKey(Trip, related_name="route_options", on_delete=models.CASCADE)

    provider_route_index = models.IntegerField()
    """Index of this alternative in the routing provider's response."""

    distance_mi = models.FloatField()
    travel_time_hr = models.FloatField()

    geometry = models.JSONField()
    """List of [lon, lat] coordinates describing the route polyline."""

    checkpoints = models.JSONField()
    """Serialized per-checkpoint assessments in route order."""

    metrics = models.JSONField()
    """Serialized RouteRiskMetrics for this alternative."""

    rank = models.IntegerField(null=True, blank=True)
    """One-based rank among eligible routes; null when ineligible."""

    is_recommended = models.BooleanField(default=False)

    ineligible_reason = models.CharField(max_length=100, blank=True, default="")
    """Reason code when excluded (e.g. ROUTE_NO_TRAVEL_EXPOSURE), else empty."""

    class Meta:
        ordering = ["trip", "provider_route_index"]

    def __str__(self) -> str:
        return f"Trip {self.trip_id} option {self.provider_route_index}"
