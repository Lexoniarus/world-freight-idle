"""Nominatim geocoding adapter."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.domain.cache_ports import ProviderCache
from app.domain.errors import GeocodingError
from app.providers.validation import parse_coordinates
from app.tracing import get_trace_id

LOGGER = logging.getLogger(__name__)


class NominatimGeocoder:
    """Low-volume cached geocoder for the fixed MVP address pool."""

    def __init__(
        self,
        cache: ProviderCache,
        client: httpx.AsyncClient,
        base_url: str,
        user_agent: str,
        minimum_interval_seconds: float = 1.05,
    ) -> None:
        self.cache = cache
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.minimum_interval_seconds = minimum_interval_seconds
        self._lock = asyncio.Lock()
        self._last_request_monotonic = 0.0

    async def geocode(self, address: str) -> tuple[float, float, str]:
        """Normalize transport and malformed-response errors at the port."""
        try:
            return await self._resolve_address(address)
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
        ) as exc:
            raise GeocodingError(
                "Geocoding-Anbieter nicht verfügbar."
            ) from exc

    async def _resolve_address(self, address: str) -> tuple[float, float, str]:
        """Resolve one postal address, using the persistent cache first."""
        cached = self.cache.get_geocode(address)
        if cached:
            LOGGER.info(
                "Geocode cache hit",
                extra={
                    "event": "geocode.cache_hit",
                    "data": {"address": address},
                },
            )
            try:
                lon, lat = parse_coordinates([cached["lon"], cached["lat"]])
                return lat, lon, str(cached["display_name"])
            except (ValueError, TypeError, KeyError):
                LOGGER.warning(
                    "Invalid cached geocode",
                    extra={"event": "geocode.cache_invalid"},
                )

        async with self._lock:
            await self._respect_rate_limit()
            LOGGER.info(
                "Geocoding address",
                extra={
                    "event": "geocode.request",
                    "data": {"address": address},
                },
            )
            response = await self.client.get(
                f"{self.base_url}/search",
                params={
                    "q": address,
                    "format": "jsonv2",
                    "limit": 1,
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": self.user_agent,
                    "X-Trace-Id": get_trace_id(),
                },
            )
            self._last_request_monotonic = time.monotonic()
            response.raise_for_status()
            data = response.json()
        if not data:
            raise GeocodingError(
                f"Adresse konnte nicht geocodiert werden: {address}"
            )

        if not isinstance(data, list) or not isinstance(data[0], dict):
            raise ValueError("Expected geocoding result objects")
        first = data[0]
        lon, lat = parse_coordinates([first["lon"], first["lat"]])
        display_name = str(first.get("display_name") or address)
        self.cache.put_geocode(address, lat, lon, display_name)
        return lat, lon, display_name

    async def _respect_rate_limit(self) -> None:
        """Serialize public Nominatim requests and enforce a minimum gap."""
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self.minimum_interval_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
