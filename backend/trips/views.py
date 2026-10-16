from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from trips.serializers import TripRequestSerializer
from trips.service import PlanningError, plan_trip


@api_view(["POST"])
def root(request: Request) -> Response:
    """Plan a trip.

    Body: start, end, load_lb, depart_at (ISO 8601), sample_miles (10, 25, or 50).
    """
    serializer = TripRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        payload = plan_trip(
            start=serializer.validated_data["start"],
            end=serializer.validated_data["end"],
            load_lb=serializer.validated_data["load_lb"],
            depart_at=serializer.validated_data["depart_at"],
            sample_miles=serializer.validated_data["sample_miles"],
        )
    except PlanningError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(payload)
