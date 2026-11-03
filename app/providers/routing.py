"""Valhalla truck-routing adapter."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from typing import Any

import httpx

from app.domain.cache_ports import ProviderCache
from app.domain.errors import RoutingError
from app.domain.transports import RouteSnapshot
from app.providers.request_limiter import ProviderRequestLimiter
from app.providers.valhalla_metadata import graph_revision
from app.providers.valhalla_response import ValhallaResponseParser
from app.providers.validation import validate_route
from app.tracing import get_trace_id

LOGGER = logging.getLogger(__name__)


class ValhallaTruckRouter:
    """Route trucks on the real OpenStreetMap road graph via Valhalla."""

    def __init__(
        self,
        cache: ProviderCache,
        client: httpx.AsyncClient,
        base_url: str,
        client_id: str,
        limiter: ProviderRequestLimiter | None = None,
        revision_observer: Callable[[str], None] | None = None,
        cache_enabled: bool = True,
        response_parser: ValhallaResponseParser | None = None,
    ) -> None:
        """Inject HTTP, cache, pacing and observed revision boundaries."""
        self.cache = cache
        self.cache_enabled = cache_enabled
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.revision_observer = revision_observer
        self.limiter = limiter or ProviderRequestLimiter(1, 1.0)
        self.response_parser = response_parser or ValhallaResponseParser()

    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteSnapshot:
        """Normalize transport and malformed-response errors at the port."""
        error: RoutingError
        cause: Exception | None = None
        try:
            return await self._resolve_route(
                origin_lat, origin_lon, destination_lat, destination_lon
            )
        except RoutingError as exc:
            error = exc
        except httpx.HTTPError as exc:
            error = RoutingError("Routing-Anbieter nicht verfügbar.")
            error.category = "provider_unavailable"
            error.provider_message = str(exc)
            error.retryable = True
            cause = exc
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            error = RoutingError(
                "Routing-Anbieter lieferte eine ungültige Antwort."
            )
            error.category = "invalid_response"
            error.provider_message = str(exc)
            error.retryable = False
            cause = exc

        LOGGER.warning(
            "Routing failed",
            extra={
                "event": "route.failure",
                "data": {
                    "category": error.category,
                    "provider_code": error.provider_code,
                    "provider_message": error.provider_message,
                    "retryable": error.retryable,
                },
            },
        )
        if cause is None:
            raise error
        raise error from cause

    async def _resolve_route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteSnapshot:
        """Fetch or reuse a real truck route between two coordinates."""
        cache_key = self._build_cache_key(
            origin_lat,
            origin_lon,
            destination_lat,
            destination_lon,
        )
        cached = self._read_cached_route(cache_key)
        if cached is not None:
            return cached
        response = await self._request_route(
            origin_lat,
            origin_lon,
            destination_lat,
            destination_lon,
        )
        self._observe_response(response)
        if response.status_code >= 400:
            raise self.response_parser.provider_error(response)
        payload = self.response_parser.response_payload(response)
        route_result = self.response_parser.extract_route(payload)
        if self.cache_enabled:
            self.cache.put_route(
                cache_key,
                route_cache_document(route_result),
            )
        return route_result

    def _read_cached_route(self, cache_key: str) -> RouteSnapshot | None:
        """Return one valid cached route and reject corrupt documents."""
        try:
            cached = (
                self.cache.get_route(cache_key) if self.cache_enabled else None
            )
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
                return validate_route(cached)
            except (ValueError, TypeError, KeyError):
                LOGGER.warning(
                    "Invalid cached route",
                    extra={"event": "route.cache_invalid"},
                )
        return None

    async def _request_route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> httpx.Response:
        """Submit one rate-limited truck request to Valhalla."""
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
        async with self.limiter.request():
            return await self.client.post(
                f"{self.base_url}/route",
                json=body,
                headers={
                    "X-Client-Id": self.client_id,
                    "X-Trace-Id": get_trace_id(),
                },
            )

    def _observe_response(self, response: httpx.Response) -> None:
        """Publish provider pacing and graph-revision metadata."""
        self.limiter.defer(response.headers.get("Retry-After"))
        revision = graph_revision(response.headers)
        if revision and self.revision_observer:
            self.revision_observer(revision)

    def _build_cache_key(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> str:
        """Create a stable cache key for one directed truck route."""
        raw = (
            f"truck:v2:{self.base_url}:"
            f"{origin_lat:.6f},{origin_lon:.6f}:"
            f"{destination_lat:.6f},{destination_lon:.6f}:v1"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def route_cache_document(route: RouteSnapshot) -> dict[str, Any]:
    """Encode the provider cache document at its I/O boundary."""
    return {
        "distance_km": route.distance_km,
        "duration_seconds": route.duration_seconds,
        "provider": route.provider,
        "route_geojson": {
            "type": "LineString",
            "coordinates": [list(point) for point in route.coordinates],
        },
    }
