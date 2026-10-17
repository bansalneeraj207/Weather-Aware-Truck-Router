"""Serializers for trip planning requests."""

from __future__ import annotations

from rest_framework import serializers

from trips.sampling import SAMPLE_MILES


class TripRequestSerializer(serializers.Serializer):
    """Request payload for POST /api/trips/."""

    start = serializers.CharField(max_length=200)
    end = serializers.CharField(max_length=200)
    load_lb = serializers.FloatField(min_value=0)
    depart_at = serializers.DateTimeField()
    sample_miles = serializers.ChoiceField(choices=SAMPLE_MILES)

    def validate_start(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("start must be a non-empty place name.")
        return value

    def validate_end(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("end must be a non-empty place name.")
        return value

    def validate_load_lb(self, value: float) -> float:
        if value <= 0:
            raise serializers.ValidationError("load_lb must be > 0.")
        return value

    def validate_sample_miles(self, value: int) -> int:
        if value not in SAMPLE_MILES:
            raise serializers.ValidationError("sample_miles must be one of: 10, 25, 50.")
        return value
