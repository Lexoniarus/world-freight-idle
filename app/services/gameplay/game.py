"""Thin player-game facade over explicit application services."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.market import VehicleCoverageDiagnostic
from app.domain.market_preparation import PreparationStatus
from app.domain.results import (
    AvailableContract,
    ContractQuote,
    GameSnapshot,
    MarketPresentation,
)
from app.domain.state_ports import GameStateRepository, GameUnitOfWork
from app.domain.transports import ActiveTransport
from app.services.gameplay.dispatch import TransportDispatchService
from app.services.gameplay.initialization import PlayerInitializationService
from app.services.gameplay.settlement import TransportSettlementService
from app.services.market.lifecycle import MarketLifecycleService
from app.services.market.player_services import PlayerMarketServices


@dataclass
class GameService:
    """Expose player use cases while delegating stateful workflows."""

    unit_of_work: GameUnitOfWork
    now: Callable[[], float]
    time_scale: float
    market_lifecycle: MarketLifecycleService
    initialization: PlayerInitializationService
    settlement: TransportSettlementService
    transport_dispatch: TransportDispatchService
    market_services: PlayerMarketServices
    state_repository: GameStateRepository = field(init=False)

    def __post_init__(self) -> None:
        """Normalize timing and expose the repository read boundary."""
        self.time_scale = max(0.001, self.time_scale)
        self.state_repository = self.unit_of_work.repository

    def ensure_initial_state(self) -> None:
        """Create missing player state through its dedicated service."""
        self.initialization.ensure()

    def preparation_status(self) -> PreparationStatus | None:
        """Expose typed progress for the authenticated player's market."""
        return self.market_services.demand.status()

    async def quote_contract(
        self, contract_id: str, vehicle_id: str
    ) -> ContractQuote:
        """Quote one contract through the dispatch boundary."""
        return await self.transport_dispatch.quote_contract(
            contract_id,
            vehicle_id,
        )

    async def dispatch(
        self,
        contract_id: str,
        vehicle_id: str,
    ) -> ActiveTransport:
        """Dispatch one contract through the atomic transport service."""
        return await self.transport_dispatch.dispatch(contract_id, vehicle_id)

    def reconcile_arrival(self) -> bool:
        """Settle due transports through the settlement boundary."""
        return self.settlement.reconcile()

    def player_state(self) -> PlayerState:
        """Return initialized player economy state."""
        return self.settlement.player_state()

    def state(self) -> GameSnapshot:
        """Synchronize and read the complete player-owned state."""
        arrived = self.reconcile_arrival()
        if not arrived:
            self.market_lifecycle.published()
        with self.unit_of_work.read_transaction():
            return GameSnapshot(
                self.now(),
                self.time_scale,
                self.player_state(),
                self.state_repository.list_vehicles(),
                self.state_repository.list_active_transports(),
                self.state_repository.list_offers(),
            )

    def dashboard(self) -> GameSnapshot:
        """Read startup state without generating a contract market."""
        self.reconcile_arrival()
        with self.unit_of_work.read_transaction():
            return GameSnapshot(
                self.now(),
                self.time_scale,
                self.player_state(),
                self.state_repository.list_vehicles(),
                self.state_repository.list_active_transports(),
            )

    def list_contracts(self) -> list[ContractOffer]:
        """Reconcile arrivals and return already published local stock."""
        self.reconcile_arrival()
        return self.market_lifecycle.published()

    def refresh_contracts(self) -> list[ContractOffer]:
        """Request background refill and return already published stock."""
        self.reconcile_arrival()
        return self.market_lifecycle.published(refresh=True)

    def read_market(
        self,
        vehicle_id: str,
        *,
        refresh: bool = False,
    ) -> MarketPresentation:
        """Reconcile and read one vehicle market through one snapshot."""
        self.reconcile_arrival()
        return self.market_lifecycle.read_market(
            vehicle_id,
            refresh=refresh,
        )

    def contract_choices(
        self, offers: Sequence[ContractOffer], vehicle_id: str | None = None
    ) -> tuple[AvailableContract, ...]:
        """Expose server-side vehicle choices for already read offers."""
        return self.market_lifecycle.present(offers, vehicle_id)

    def market_presentation(
        self,
        offers: Sequence[ContractOffer],
        vehicle_id: str,
    ) -> MarketPresentation:
        """Read authorized offers and diagnostics in one local transaction."""
        with self.unit_of_work.read_transaction():
            contracts = self.contract_choices(offers, vehicle_id)
            coverage = tuple(
                item
                for item in self.vehicle_coverage()
                if item.vehicle_id == vehicle_id
            )
            return MarketPresentation(
                contracts,
                coverage,
                self.preparation_status(),
            )

    def vehicle_coverage(self) -> tuple[VehicleCoverageDiagnostic, ...]:
        """Delegate actual per-vehicle coverage diagnostics."""
        return self.market_lifecycle.vehicle_diagnostics()

    def get_contract(self, contract_id: str) -> ContractOffer:
        """Return one available offer with historical endpoint values."""
        self.list_contracts()
        return self.transport_dispatch.find_contract(contract_id)

    def list_vehicles(self) -> tuple[OwnedVehicle, ...]:
        """Return owned vehicles after settling any due deliveries."""
        self.reconcile_arrival()
        return self.state_repository.list_vehicles()

    def get_vehicle(self, vehicle_id: str) -> OwnedVehicle:
        """Find one owned vehicle or report a missing resource."""
        vehicle = next(
            (
                item
                for item in self.state_repository.list_vehicles()
                if item.id == vehicle_id
            ),
            None,
        )
        if vehicle is None:
            raise KeyError("Fahrzeug nicht gefunden")
        return vehicle

    def list_transports(self) -> tuple[ActiveTransport, ...]:
        """Return pending deliveries after settling due arrivals."""
        self.reconcile_arrival()
        return self.state_repository.list_active_transports()

    def get_transport(self, transport_id: str) -> ActiveTransport:
        """Find a pending transport owned by the current player."""
        self.reconcile_arrival()
        trip = next(
            (
                item
                for item in self.state_repository.list_active_transports()
                if item.id == transport_id
            ),
            None,
        )
        if trip is None:
            raise KeyError("Transport nicht gefunden")
        return trip

    def reset(self) -> GameSnapshot:
        """Reset player progress while retaining provider caches."""
        self.initialization.reset()
        return self.state()
