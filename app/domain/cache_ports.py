"""Cache contracts for provider adapters and offline enrichment."""

from typing import Any, Protocol


class ProviderCache(Protocol):
    """Store provider documents without exposing SQLite to HTTP adapters."""

    def get_route(self, cache_key: str) -> dict[str, Any] | None: ...

    def put_route(self, cache_key: str, payload: dict[str, Any]) -> None: ...

    def get_geocode(self, address: str) -> dict[str, Any] | None: ...

    def put_geocode(
        self, address: str, lat: float, lon: float, display_name: str
    ) -> None: ...
