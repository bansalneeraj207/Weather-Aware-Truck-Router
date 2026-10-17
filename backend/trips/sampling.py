"""Route checkpoint sampling using GeographicLib's geodesic helpers.

This is a smaller alternative to :mod:`trips.sampling`.  Coordinates are
``[longitude, latitude]`` as returned by the routing provider.  GeographicLib
does the Earth-distance and point-along-a-leg calculations, so this module
doesn't need to implement Haversine or coordinate interpolation itself.
"""

from __future__ import annotations

from geographiclib.geodesic import Geodesic

SAMPLE_MILES = (10, 25, 50)


CHECKPOINT_SPACING_MI = 25.0
METERS_PER_MILE = 1609.344


def sample_checkpoints(
    coords: list[list[float]],
    spacing_mi: float = CHECKPOINT_SPACING_MI,
) -> list[dict]:
    """Return route start, evenly spaced checkpoints, and route end.

    Each checkpoint is ``{"lat", "lon", "distance_mi"}``.  Distances are
    measured along the supplied route geometry rather than directly between
    its endpoints.
    """
    if not coords:
        return []
    if spacing_mi <= 0:
        raise ValueError("Checkpoint spacing must be greater than zero.")

    start_lon, start_lat = coords[0]
    checkpoints = [{"lat": start_lat, "lon": start_lon, "distance_mi": 0.0}]
    next_checkpoint_mi = spacing_mi
    distance_so_far_mi = 0.0

    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        # InverseLine gives both the leg length and any point on that leg.
        leg = Geodesic.WGS84.InverseLine(lat1, lon1, lat2, lon2)
        leg_mi = leg.s13 / METERS_PER_MILE

        while distance_so_far_mi + leg_mi >= next_checkpoint_mi:
            position = leg.Position(
                (next_checkpoint_mi - distance_so_far_mi) * METERS_PER_MILE,
                Geodesic.LATITUDE | Geodesic.LONGITUDE,
            )
            checkpoints.append(
                {
                    "lat": position["lat2"],
                    "lon": position["lon2"],
                    "distance_mi": next_checkpoint_mi,
                }
            )
            next_checkpoint_mi += spacing_mi

        distance_so_far_mi += leg_mi

    end_lon, end_lat = coords[-1]
    if checkpoints[-1]["distance_mi"] < distance_so_far_mi - 1e-6:
        checkpoints.append(
            {"lat": end_lat, "lon": end_lon, "distance_mi": distance_so_far_mi}
        )
    return checkpoints


def polyline_distance_mi(coords: list[list[float]]) -> float:
    """Return the total geodesic length of a provider route geometry."""
    return sum(
        Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)["s12"] / METERS_PER_MILE
        for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:])
    )


def segment_lengths_mi(checkpoints: list[dict]) -> list[float]:
    """Return the route length represented by every consecutive checkpoint pair."""
    return [
        following["distance_mi"] - current["distance_mi"]
        for current, following in zip(checkpoints, checkpoints[1:])
    ]
