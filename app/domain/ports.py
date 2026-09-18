"""Provider interfaces consumed by application services."""

from typing import Protocol

from app.domain.models import RouteResult, VehicleModel


class Geocoder(Protocol):
    """Port required by the game service for address resolution."""

    async def geocode(self, address: str) -> tuple[float, float, str]:
        """Resolve one textual address."""


class TruckRouter(Protocol):
    """Port required by the game service for road routing."""

    async def route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> RouteResult:
        """Route one truck trip."""


class VehicleCatalogue(Protocol):
    """Read validated purchase offers without modifying reference data."""

    def list_models(self) -> tuple[VehicleModel, ...]:
        """Return offers sorted by game price and stable model ID."""
