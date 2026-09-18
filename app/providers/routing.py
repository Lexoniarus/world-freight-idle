"""Valhalla truck-routing adapter."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx

from app.domain.errors import RoutingError
from app.domain.models import RouteResult
from app.providers.validation import validate_route
from app.repositories.sqlite_store import SqliteStore
from app.tracing import get_trace_id

LOGGER = logging.getLogger(__name__)


def decode_polyline6(encoded: str) -> list[list[float]]:
    """Decode Valhalla polyline6 into GeoJSON [lon, lat] coordinates."""
    coordinates: list[list[float]] = []
    index = 0
    latitude = 0
    longitude = 0
    factor = 1_000_000.0

    while index < len(encoded):
        deltas: list[int] = []
        for _ in range(2):
            result = 0
            shift = 0
            while True:
                if index >= len(encoded):
                    raise RoutingError("Ungültige Valhalla-Polyline.")
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            deltas.append(delta)
        latitude += deltas[0]
        longitude += deltas[1]
        coordinates.append([longitude / factor, latitude / factor])

    return coordinates


class ValhallaTruckRouter:
    """Route trucks on the real OpenStreetMap road graph via Valhalla."""

    def __init__(
        self,
        store: SqliteStore,
        client: httpx.AsyncClient,
        base_url: str,
        client_id: str,
    ) -> None:
        self.store = store
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id

    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteResult:
        """Normalize transport and malformed-response errors at the port."""
        try:
            return await self._resolve_route(
                origin_lat, origin_lon, destination_lat, destination_lon
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RoutingError("Routing-Anbieter nicht verfügbar.") from exc

    async def _resolve_route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteResult:
        """Fetch or reuse a real truck route between two coordinates."""
        cache_key = self._build_cache_key(
            origin_lat,
            origin_lon,
            destination_lat,
            destination_lon,
        )
        try:
            cached = self.store.get_route(cache_key)
        except ValueError:
            LOGGER.warning(
                "Unreadable cached route",
                extra={"event": "route.cache_invalid"},
            )
            cached = None
        if cached:
            LOGGER.info(
                "Route cache hit",
                extra={"event": "route.cache_hit", "data": {"key": cache_key}},
            )
            try:
                return validate_route(RouteResult(**cached))
            except (ValueError, TypeError, KeyError):
                LOGGER.warning(
                    "Invalid cached route",
                    extra={"event": "route.cache_invalid"},
                )

        body = {
            "locations": [
                {"lat": origin_lat, "lon": origin_lon},
                {"lat": destination_lat, "lon": destination_lon},
            ],
            "costing": "truck",
            "units": "kilometers",
            "shape_format": "geojson",
            "directions_options": {"units": "kilometers"},
        }
        LOGGER.info(
            "Routing truck",
            extra={
                "event": "route.request",
                "data": {
                    "origin": [origin_lat, origin_lon],
                    "destination": [destination_lat, destination_lon],
                },
            },
        )
        response = await self.client.post(
            f"{self.base_url}/route",
            json=body,
            headers={
                "X-Client-Id": self.client_id,
                "X-Trace-Id": get_trace_id(),
            },
        )
        if response.status_code >= 400:
            raise RoutingError(
                f"Valhalla HTTP {response.status_code}: {response.text[:200]}"
            )

        route_result = self._extract_route(response.json())
        self.store.put_route(cache_key, route_result.to_dict())
        return route_result

    def _build_cache_key(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> str:
        """Create a stable cache key for one directed truck route."""
        raw = (
            "truck:"
            f"{origin_lat:.6f},{origin_lon:.6f}:"
            f"{destination_lat:.6f},{destination_lon:.6f}:v1"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _extract_route(self, data: dict[str, Any]) -> RouteResult:
        """Normalize Valhalla JSON into the domain route representation."""
        try:
            if not isinstance(data, dict):
                raise ValueError("Expected a route object")
            trip = data["trip"]
            if not isinstance(trip, dict):
                raise ValueError("Expected a trip object")
            summary = trip["summary"]
            coordinates: list[list[float]] = []
            for leg in trip["legs"]:
                if not isinstance(leg, dict):
                    raise ValueError("Expected a leg object")
                shape = leg.get("shape")
                if (
                    isinstance(shape, dict)
                    and shape.get("type") == "LineString"
                ):
                    leg_coordinates = shape["coordinates"]
                elif isinstance(shape, str):
                    leg_coordinates = decode_polyline6(shape)
                else:
                    raise RoutingError(
                        "Valhalla lieferte keine verwertbare Routengeometrie."
                    )
                if (
                    coordinates
                    and leg_coordinates
                    and coordinates[-1] == leg_coordinates[0]
                ):
                    leg_coordinates = leg_coordinates[1:]
                coordinates.extend(leg_coordinates)
        except (KeyError, TypeError, ValueError) as exc:
            preview = json.dumps(data, ensure_ascii=False)[:400]
            raise RoutingError(
                f"Unerwartete Valhalla-Antwort: {preview}"
            ) from exc

        if len(coordinates) < 2:
            raise RoutingError("Route enthält zu wenige Punkte.")

        if any(isinstance(summary[key], bool) for key in ("length", "time")):
            raise ValueError("Invalid route metric type")
        return validate_route(
            RouteResult(
                distance_km=float(summary["length"]),
                duration_seconds=float(summary["time"]),
                route_geojson={
                    "type": "LineString",
                    "coordinates": coordinates,
                },
                provider="Valhalla / OpenStreetMap (truck)",
            )
        )
