"""Validate untrusted geographic provider values before caching them."""

import math
from typing import Any

from app.domain.transports import RouteSnapshot


def parse_coordinates(value: Any) -> tuple[float, float]:
    """Return finite WGS84 longitude/latitude, rejecting invalid points."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Expected a longitude/latitude pair")
    if any(isinstance(item, bool) or item is None for item in value):
        raise ValueError("Invalid coordinate type")
    lon, lat = (float(item) for item in value)
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise ValueError("Non-finite coordinate")
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Coordinate outside WGS84 bounds")
    return lon, lat


def validate_route(value: dict[str, Any]) -> RouteSnapshot:
    """Normalize untrusted cached/provider geometry into an immutable route."""
    if not isinstance(value, dict):
        raise ValueError("Expected a route object")
    for metric in (value["distance_km"], value["duration_seconds"]):
        if (
            isinstance(metric, bool)
            or not math.isfinite(metric)
            or metric <= 0
        ):
            raise ValueError("Route metrics must be finite and positive")
    geometry = value["route_geojson"]
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise ValueError("Expected a LineString")
    points = geometry.get("coordinates")
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("Expected at least two route coordinates")
    return RouteSnapshot(
        coordinates=tuple(parse_coordinates(point) for point in points),
        distance_km=value["distance_km"],
        duration_seconds=value["duration_seconds"],
        provider=value["provider"],
    )
