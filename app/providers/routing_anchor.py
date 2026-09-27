"""Valhalla truck-locate adapter for facility routing anchors."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

import httpx

from app.domain.geography import Coordinates
from app.domain.routing_anchors import LocateResult, RoutingAnchorStatus
from app.providers.request_limiter import ProviderRequestLimiter
from app.providers.valhalla_metadata import graph_revision
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
        limiter: ProviderRequestLimiter | None = None,
        revision_observer: Callable[[str], None] | None = None,
    ) -> None:
        """Inject truck-locate HTTP and shared provider request limits."""
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.revision_observer = revision_observer
        self.limiter = limiter or ProviderRequestLimiter(1, 1.0)

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
            async with self.limiter.request():
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
            self.limiter.defer(response.headers.get("Retry-After"))
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
                provider_message=str(exc),
            )

        revision = self._revision(response.headers)
        if revision and self.revision_observer:
            self.revision_observer(revision)
        if response.status_code >= 500 or response.status_code in {408, 429}:
            return self._response_failure(
                response, "provider_unavailable", revision
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
            return self._response_failure(
                response,
                "no_truck_edge" if no_edge else "invalid_response",
                revision,
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
            candidates = self._access_candidates(correlated["edges"])
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
            candidates=candidates,
        )

    @staticmethod
    def _response_failure(
        response: httpx.Response,
        status: RoutingAnchorStatus,
        revision: str | None,
    ) -> LocateResult:
        """Retain bounded provider evidence for append-only diagnostics."""
        code = None
        try:
            data = response.json()
            if isinstance(data, dict) and type(data.get("error_code")) is int:
                code = data["error_code"]
        except ValueError:
            pass
        return LocateResult(
            False,
            None,
            None,
            PROVIDER,
            revision,
            status,
            provider_code=code,
            provider_message=response.text[:400] or None,
        )

    @staticmethod
    def _access_candidates(
        edges: list[dict[str, Any]],
    ) -> tuple[Coordinates, ...]:
        """Retain at most five distinct truck-compatible OSM correlations."""
        candidates: list[Coordinates] = []
        for edge in edges:
            if edge.get("access", {}).get("truck") is False:
                continue
            candidate = Coordinates(
                float(edge["correlated_lat"]), float(edge["correlated_lon"])
            )
            if candidate not in candidates:
                candidates.append(candidate)
            if len(candidates) == 5:
                break
        return tuple(candidates)

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
        return graph_revision(headers)
