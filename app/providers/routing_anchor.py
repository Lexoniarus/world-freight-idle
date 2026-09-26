"""Valhalla truck-locate adapter for facility routing anchors."""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from app.domain.geography import Coordinates
from app.domain.routing_anchors import LocateResult
from app.tracing import get_trace_id

LOGGER = logging.getLogger(__name__)
PROVIDER = "Valhalla / OpenStreetMap (truck locate)"


class ValhallaTruckAnchorLocator:
    """Correlate candidate coordinates with Valhalla's truck graph."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        client_id: str,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id

    async def locate(self, coordinates: Coordinates) -> LocateResult:
        """Validate a candidate without inventing coordinates."""
        LOGGER.info(
            "Locating truck routing anchor",
            extra={
                "event": "routing_anchor.locate_request",
                "data": {
                    "latitude": coordinates.latitude,
                    "longitude": coordinates.longitude,
                },
            },
        )
        try:
            response = await self.client.post(
                f"{self.base_url}/locate",
                json={
                    "locations": [
                        {
                            "lat": coordinates.latitude,
                            "lon": coordinates.longitude,
                        }
                    ],
                    "costing": "truck",
                    "verbose": True,
                },
                headers={
                    "X-Client-Id": self.client_id,
                    "X-Trace-Id": get_trace_id(),
                },
            )
        except httpx.HTTPError as exc:
            LOGGER.warning(
                "Truck anchor provider unavailable",
                extra={
                    "event": "routing_anchor.provider_unavailable",
                    "data": {"message": str(exc)},
                },
            )
            return LocateResult(
                accepted=False,
                coordinates=None,
                snap_distance_m=None,
                provider=PROVIDER,
                provider_revision=None,
                status="provider_unavailable",
            )

        revision = self._revision(response.headers)
        if response.status_code >= 500 or response.status_code in {408, 429}:
            return LocateResult(
                accepted=False,
                coordinates=None,
                snap_distance_m=None,
                provider=PROVIDER,
                provider_revision=revision,
                status="provider_unavailable",
            )
        if response.status_code >= 400:
            normalized = response.text.casefold()
            no_edge = any(
                marker in normalized
                for marker in (
                    "no suitable edges",
                    "no data found for location",
                    "location is unreachable",
                )
            )
            return LocateResult(
                accepted=False,
                coordinates=None,
                snap_distance_m=None,
                provider=PROVIDER,
                provider_revision=revision,
                status="no_truck_edge" if no_edge else "invalid_response",
            )

        try:
            payload = response.json()
            correlated = self._correlated_location(payload)
            if self._edge_count(correlated) < 1:
                return LocateResult(
                    accepted=False,
                    coordinates=None,
                    snap_distance_m=None,
                    provider=PROVIDER,
                    provider_revision=revision,
                    status="no_truck_edge",
                )
            anchor = Coordinates(
                float(correlated["lat"]),
                float(correlated["lon"]),
            )
            distance = self._snap_distance_m(coordinates, anchor)
        except (ValueError, KeyError, TypeError, IndexError):
            return LocateResult(
                accepted=False,
                coordinates=None,
                snap_distance_m=None,
                provider=PROVIDER,
                provider_revision=revision,
                status="invalid_response",
            )

        return LocateResult(
            accepted=True,
            coordinates=anchor,
            snap_distance_m=distance,
            provider=PROVIDER,
            provider_revision=revision,
            status="validated",
        )

    @staticmethod
    def _correlated_location(payload: Any) -> dict[str, Any]:
        """Extract the closest correlated edge from a locate response."""
        if not isinstance(payload, list) or not payload:
            raise ValueError("Unsupported locate payload.")
        location = payload[0]
        if not isinstance(location, dict):
            raise ValueError("Invalid locate location.")
        edges = location.get("edges")
        if not isinstance(edges, list):
            raise ValueError("Invalid locate edges.")
        if not edges:
            return {"edges": []}
        edge = edges[0]
        if not isinstance(edge, dict):
            raise ValueError("Invalid locate edge.")
        return {
            "lat": edge["correlated_lat"],
            "lon": edge["correlated_lon"],
            "edges": edges,
        }

    @staticmethod
    def _edge_count(location: dict[str, Any]) -> int:
        """Count correlated truck-compatible edges."""
        edges = location.get("edges")
        if not isinstance(edges, list):
            return 0
        return len(edges)

    @staticmethod
    def _snap_distance_m(
        candidate: Coordinates,
        anchor: Coordinates,
    ) -> float:
        """Calculate great-circle distance between candidate and anchor."""
        radius_m = 6_371_008.8
        latitude_one = math.radians(candidate.latitude)
        latitude_two = math.radians(anchor.latitude)
        latitude_delta = latitude_two - latitude_one
        longitude_delta = math.radians(anchor.longitude - candidate.longitude)
        haversine = (
            math.sin(latitude_delta / 2) ** 2
            + math.cos(latitude_one)
            * math.cos(latitude_two)
            * math.sin(longitude_delta / 2) ** 2
        )
        return radius_m * 2 * math.asin(math.sqrt(haversine))

    @staticmethod
    def _revision(headers: httpx.Headers) -> str | None:
        """Read a provider or graph revision only when supplied."""
        for key in ("x-valhalla-version", "x-graph-revision"):
            value = headers.get(key)
            if value:
                return value
        return None
