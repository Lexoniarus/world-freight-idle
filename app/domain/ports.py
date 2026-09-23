"""Provider interfaces consumed by application services."""

from collections.abc import Callable
from typing import Any, Protocol

from app.domain.models import VehicleModel
from app.domain.transports import RouteSnapshot
from app.domain.world import WorldSnapshot


class Geocoder(Protocol):
    """Offline import/enrichment port; never part of game lookups."""

    async def geocode(self, address: str) -> tuple[float, float, str]:
        """Resolve one textual address."""
        ...


class TruckRouter(Protocol):
    """Port required by the game service for road routing."""

    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteSnapshot:
        """Route one truck trip."""
        ...


class VehicleCatalogue(Protocol):
    """Read validated purchase offers without modifying reference data."""

    def list_models(self) -> tuple[VehicleModel, ...]:
        """Return offers sorted by game price and stable model ID."""
        ...


class WorldCatalogue(Protocol):
    """Read consistent real-world references without changing them."""

    def read(self) -> "WorldSnapshot":
        """Return validated identities, endpoints and provenance."""
        ...


class WorldMaintenanceStore(Protocol):
    """Offline atomic reference maintenance boundary."""

    def upgrade(self, entries: list[dict[str, Any]]) -> None:
        """Preserve identity and reject incomplete upgrades."""
        ...


class WorldStateStore(Protocol):
    """Atomic transformation boundary for existing player records."""

    def transform(
        self,
        convert: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> int:
        """Apply the complete transformation or preserve all prior records."""
        ...
