"""Stable facade for strict offline historical snapshot decoding."""

from typing import Any

from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.game import OwnedVehicle
from app.domain.transports import ActiveTransport
from app.domain.vehicles import VehicleModel
from app.domain.world import FacilityLocationSnapshot
from app.domain.world_scopes import WorldScope
from app.repositories.legacy_snapshot import (
    LegacyContractReader,
    LegacyLocationReader,
    LegacyTransportReader,
    LegacyVehicleReader,
)


class LegacySnapshotReader:
    """Delegate each historical document type to its focused decoder."""

    def __init__(
        self, world: WorldScope, models: tuple[VehicleModel, ...]
    ) -> None:
        """Compose strict decoders around one canonical world snapshot."""
        locations = LegacyLocationReader(world)
        contracts = LegacyContractReader(locations)
        self.world = world
        self.models = {model.id: model for model in models}
        self._locations = locations
        self._vehicles = LegacyVehicleReader(
            world,
            self.models,
            locations,
        )
        self._contracts = contracts
        self._transports = LegacyTransportReader(locations, contracts)

    def read_location(
        self, value: dict[str, Any], path: str = "location"
    ) -> FacilityLocationSnapshot:
        """Restore one historical facility location."""
        return self._locations.read(value, path)

    def read_vehicle(
        self, value: dict[str, Any], path: str = "vehicle"
    ) -> OwnedVehicle:
        """Restore one historical owned vehicle."""
        return self._vehicles.read(value, path)

    def read_offer(
        self, value: dict[str, Any], path: str = "offer"
    ) -> ContractOffer:
        """Restore one current-format historical offer."""
        return self._contracts.read_offer(value, path)

    def validate_obsolete_offer(
        self, value: dict[str, Any], path: str = "offer"
    ) -> None:
        """Validate one retired offer without importing it."""
        self._contracts.validate_obsolete_offer(value, path)

    def read_historical_contract(
        self, value: dict[str, Any], path: str = "contract"
    ) -> HistoricalContractSnapshot:
        """Restore an embedded historical contract snapshot."""
        return self._contracts.read_historical_contract(value, path)

    def read_transport(
        self, value: dict[str, Any], path: str = "transport"
    ) -> ActiveTransport:
        """Restore one historical transport without rerouting."""
        return self._transports.read(value, path)
