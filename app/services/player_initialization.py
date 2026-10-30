"""Initialize one player's durable game state."""

from dataclasses import dataclass

from app.domain.game import PlayerState
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.state_ports import GameUnitOfWork
from app.services.fleet import (
    create_starter_vehicle,
    resolve_delivery_facility,
)
from app.services.player_market_demand import PlayerMarketDemandService


@dataclass(slots=True)
class PlayerInitializationService:
    """Own atomic creation and reset of the player aggregate."""

    unit: GameUnitOfWork
    world: WorldCatalogue
    catalogue: VehicleCatalogue
    market_demand: PlayerMarketDemandService | None = None

    def ensure(self) -> None:
        """Create missing player and starter state atomically."""
        repository = self.unit.repository
        if repository.get_player() is not None and repository.list_vehicles():
            return
        with self.unit.transaction():
            self.ensure_in_transaction()
            if self.market_demand is not None:
                self.market_demand.invalidate()

    def ensure_in_transaction(self) -> None:
        """Create missing state inside the caller's transaction."""
        repository = self.unit.repository
        if repository.get_player() is None:
            repository.save_player(PlayerState(175000, 0, 0))
        if not repository.list_vehicles():
            repository.save_vehicle(
                create_starter_vehicle(
                    self.catalogue,
                    resolve_delivery_facility(self.world),
                )
            )

    def reset(self) -> None:
        """Reset player state while retaining shared provider caches."""
        with self.unit.transaction():
            self.unit.repository.reset()
            self.ensure_in_transaction()
            if self.market_demand is not None:
                self.market_demand.invalidate()
