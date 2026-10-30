"""Settle completed transports without owning market presentation."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.domain.game import PlayerState
from app.domain.state_ports import GameUnitOfWork
from app.domain.transports import ActiveTransport
from app.services.player_market_demand import PlayerMarketDemandService

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TransportSettlementService:
    """Own atomic arrival reconciliation and player settlement."""

    unit: GameUnitOfWork
    clock: Callable[[], float]
    market_demand: PlayerMarketDemandService

    def reconcile(self) -> bool:
        """Settle every due transport once and request destination stock."""
        repository = self.unit.repository
        if not repository.list_due_transports(self.clock()):
            return False
        with self.unit.transaction():
            now = self.clock()
            arrived = repository.list_due_transports(now)
            if not arrived:
                return False
            for trip in arrived:
                self.complete_trip(trip, now)
            self.market_demand.invalidate()
        return True

    def complete_trip(self, trip: ActiveTransport, now: float) -> None:
        """Persist vehicle, counters and settlement in one transaction."""
        repository = self.unit.repository
        settled = trip.settle(now)
        vehicle = next(
            (
                item
                for item in repository.list_vehicles()
                if item.id == trip.vehicle_id
            ),
            None,
        )
        if vehicle is None:
            raise ValueError("Fahrzeug existiert nicht.")
        if trip.journey.energy is not None and (
            vehicle.energy != trip.journey.energy
            or vehicle.energy_level != trip.journey.segments[0].start_energy
        ):
            raise ValueError("Vehicle energy checkpoint differs from trip.")
        vehicle.arrive(trip.destination, trip.journey.segments[-1].end_energy)
        player = self.player_state()
        player.complete_delivery(trip.payout_eur)
        repository.save_vehicle(vehicle)
        repository.save_player(player)
        repository.save_transport(settled)
        LOGGER.info(
            "Trip completed",
            extra={
                "event": "trip.complete",
                "data": {
                    "trip_id": trip.id,
                    "vehicle_id": trip.vehicle_id,
                    "payout_eur": trip.payout_eur,
                },
            },
        )

    def player_state(self) -> PlayerState:
        """Require initialized economy state at the use-case boundary."""
        player = self.unit.repository.get_player()
        if player is None:
            raise ValueError("Spielstand ist nicht initialisiert.")
        return player
