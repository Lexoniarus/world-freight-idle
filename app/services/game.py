"""High-level game orchestration."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence

from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.ports import TruckRouter, VehicleCatalogue, WorldCatalogue
from app.domain.results import AvailableContract, ContractQuote, GameSnapshot
from app.domain.routes import DispatchRoutePlan
from app.domain.state_ports import GameUnitOfWork
from app.domain.transports import ActiveTransport
from app.domain.world_scopes import WorldScope
from app.services.dispatch_planning import DispatchPlanningService
from app.services.fleet import (
    create_starter_vehicle,
    resolve_delivery_facility,
)
from app.services.market import MarketGenerator
from app.services.market_lifecycle import MarketLifecycleService
from app.services.market_scope import MarketScopeResolver

LOGGER = logging.getLogger(__name__)


class GameService:
    """Orchestrate market, routing, dispatch and idle-time reconciliation."""

    def __init__(
        self,
        unit_of_work: GameUnitOfWork,
        world: WorldCatalogue,
        router: TruckRouter,
        market: MarketGenerator,
        catalogue: VehicleCatalogue,
        market_scope: MarketScopeResolver,
        clock: Callable[[], float],
        dispatch_planning: DispatchPlanningService,
        time_scale: float = 1.0,
    ) -> None:
        """Wire player-scoped orchestration to injected service ports."""
        self.unit_of_work = unit_of_work
        self.state_repository = unit_of_work.repository
        self.world = world
        self.router = router
        self.dispatch_planning = dispatch_planning
        self.market = market
        self.time_scale = max(0.001, time_scale)
        self.catalogue = catalogue
        self.market_scope = market_scope
        self.now = clock
        self.market_lifecycle = MarketLifecycleService(
            unit_of_work, market, market_scope, lambda: self.now()
        )

    def ensure_initial_state(self) -> None:
        """Atomically create missing state, including for direct callers."""
        with self.unit_of_work.transaction():
            self._ensure_initial_state()

    def _ensure_initial_state(self) -> None:
        """Initialize player and starter inside the caller's transaction."""
        if self.state_repository.get_player() is None:
            self.state_repository.save_player(PlayerState(175000, 0, 0))
        if not self.state_repository.list_vehicles():
            self.state_repository.save_vehicle(
                create_starter_vehicle(
                    self.catalogue, resolve_delivery_facility(self.world)
                )
            )

    def refresh_market(self, force: bool = False) -> list[ContractOffer]:
        """Delegate city market lifecycle to its transactional service."""
        return self.market_lifecycle.refresh(force)

    async def quote_contract(
        self, contract_id: str, vehicle_id: str
    ) -> ContractQuote:
        """Route snapshot coordinates and calculate simulated economics."""
        self.reconcile_arrival()
        contract = self._find_contract(contract_id)
        vehicle = self._find_vehicle(
            self.state_repository.list_vehicles(), vehicle_id
        )
        self._validate_dispatch(vehicle, contract)
        assert vehicle.location is not None
        route = await self.dispatch_planning.route(vehicle.location, contract)
        if self._find_contract(contract_id) != contract:
            raise ValueError("Auftrag wurde während der Kalkulation geändert.")
        vehicle = self.get_vehicle(vehicle_id)
        quote = self._calculate_quote(contract, route, vehicle)
        LOGGER.info(
            "Contract quoted",
            extra={
                "event": "contract.quote",
                "data": {
                    "contract_id": contract_id,
                    "distance_km": route.total_route.distance_km,
                    "duration_seconds": route.total_route.duration_seconds,
                    "origin_facility_uid": contract.origin.facility_uid,
                    "start_facility_uid": route.start.facility_uid,
                    "destination_facility_uid": (
                        contract.destination.facility_uid
                    ),
                },
            },
        )
        return quote

    async def dispatch(
        self,
        contract_id: str,
        vehicle_id: str,
    ) -> ActiveTransport:
        """Validate and start one real-time delivery."""
        self.reconcile_arrival()
        contract = self._find_contract(contract_id)
        vehicles = list(self.state_repository.list_vehicles())
        vehicle = self._find_vehicle(vehicles, vehicle_id)
        self._validate_dispatch(vehicle, contract)
        quote = await self.quote_contract(contract_id, vehicle_id)
        # Never hold a write transaction across an external API await.
        with self.unit_of_work.transaction():
            trip = self._commit_dispatch(contract_id, vehicle_id, quote)
        self.market_lifecycle.refill_after_commit()
        return trip

    def _commit_dispatch(
        self, contract_id: str, vehicle_id: str, quote: ContractQuote
    ) -> ActiveTransport:
        """Revalidate and atomically reserve the truck and funds."""
        contract = self._find_contract(contract_id)
        if contract != quote.contract:
            raise ValueError("Auftrag wurde während der Kalkulation geändert.")
        vehicle = self._find_vehicle(
            list(self.state_repository.list_vehicles()), vehicle_id
        )
        self._validate_dispatch(vehicle, contract)
        if quote.dispatch_route is None:
            raise ValueError("Dispatch requires a routed departure plan.")
        quote = self._calculate_quote(contract, quote.dispatch_route, vehicle)
        player = self._get_player()
        player.debit(quote.economics.operating_cost_eur)
        trip = self._build_trip(
            contract,
            vehicle_id,
            quote,
            self.now(),
        )
        vehicle.start_trip()
        self.state_repository.save_player(player)
        self.state_repository.save_vehicle(vehicle)
        self.state_repository.save_transport(trip)
        self.state_repository.remove_offer(contract_id)
        self.market_lifecycle.prune_in_transaction()
        LOGGER.info(
            "Trip dispatched",
            extra={
                "event": "trip.dispatch",
                "data": {
                    "trip_id": trip.id,
                    "contract_id": contract_id,
                    "vehicle_id": vehicle_id,
                    "energy_stop_count": trip.journey.stop_count,
                    "journey_seconds": trip.journey.duration_seconds,
                    "origin_facility_uid": trip.origin.facility_uid,
                    "destination_facility_uid": trip.destination.facility_uid,
                },
            },
        )
        return trip

    def reconcile_arrival(self) -> bool:
        """Settle due active transports once, before refreshing the market."""
        with self.unit_of_work.transaction():
            now = self.now()
            arrived = self.state_repository.list_due_transports(now)
            if not arrived:
                return False
            for trip in arrived:
                self._complete_trip(trip, now)
        self.market_lifecycle.refill_after_commit()
        return True

    def _complete_trip(self, trip: ActiveTransport, now: float) -> None:
        """Persist vehicle, counters and settlement in the same transaction."""
        settled = trip.settle(now)
        vehicle = self._find_vehicle(
            list(self.state_repository.list_vehicles()), trip.vehicle_id
        )
        if trip.journey.energy is not None and (
            vehicle.energy != trip.journey.energy
            or vehicle.energy_level != trip.journey.segments[0].start_energy
        ):
            raise ValueError("Vehicle energy checkpoint differs from trip.")
        vehicle.arrive(trip.destination, trip.journey.segments[-1].end_energy)
        player = self._get_player()
        player.complete_delivery(trip.payout_eur)
        self.state_repository.save_vehicle(vehicle)
        self.state_repository.save_player(player)
        self.state_repository.save_transport(settled)
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

    def _get_player(self) -> PlayerState:
        """Require initialized economy state at the use-case boundary."""
        player = self.state_repository.get_player()
        if player is None:
            raise ValueError("Spielstand ist nicht initialisiert.")
        return player

    def state(self) -> GameSnapshot:
        """Synchronize and read the complete player-owned state."""
        arrived = self.reconcile_arrival()
        if not arrived:
            self.refresh_market(force=False)
        with self.unit_of_work.transaction():
            return GameSnapshot(
                self.now(),
                self.time_scale,
                self._get_player(),
                self.state_repository.list_vehicles(),
                self.state_repository.list_active_transports(),
                self.state_repository.list_offers(),
            )

    def dashboard(self) -> GameSnapshot:
        """Read startup state without generating a contract market."""
        self.reconcile_arrival()
        with self.unit_of_work.transaction():
            return GameSnapshot(
                self.now(),
                self.time_scale,
                self._get_player(),
                self.state_repository.list_vehicles(),
                self.state_repository.list_active_transports(),
            )

    def list_contracts(self) -> list[ContractOffer]:
        """Reconcile arrivals and return retained/refilled city markets."""
        self.reconcile_arrival()
        return self.refresh_market()

    def refresh_contracts(self) -> list[ContractOffer]:
        """Explicitly regenerate offers only for current active cities."""
        self.reconcile_arrival()
        return self.refresh_market(force=True)

    def contract_choices(
        self, offers: Sequence[ContractOffer]
    ) -> tuple[AvailableContract, ...]:
        """Expose server-side vehicle choices for already read offers."""
        return self.market_lifecycle.present(offers)

    def get_contract(self, contract_id: str) -> ContractOffer:
        """Return one available offer with historical endpoint values."""
        self.list_contracts()
        return self._find_contract(contract_id)

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
        """Reset game progress while retaining external-provider caches."""
        with self.unit_of_work.transaction():
            self.state_repository.reset()
            self.ensure_initial_state()
            return self.state()

    def _find_contract(self, contract_id: str) -> ContractOffer:
        """Find a current offer using caller-owned time."""
        now = self.now()
        contract = next(
            (
                offer
                for offer in self.state_repository.list_offers()
                if offer.id == contract_id
                and offer.is_available(now, self.market.model_id)
            ),
            None,
        )
        if contract is None:
            raise KeyError("Auftrag nicht gefunden")
        return contract

    def _find_vehicle(
        self,
        vehicles: Sequence[OwnedVehicle],
        vehicle_id: str,
    ) -> OwnedVehicle:
        """Find a vehicle by ID or raise a stable validation error."""
        vehicle = next(
            (item for item in vehicles if item.id == vehicle_id),
            None,
        )
        if vehicle is None:
            raise ValueError("Fahrzeug existiert nicht.")
        return vehicle

    def _validate_dispatch(
        self,
        vehicle: OwnedVehicle,
        contract: ContractOffer,
    ) -> None:
        """Delegate vehicle-specific dispatch invariants to the entity."""
        if vehicle.location is None:
            vehicle.restore_location(
                WorldScope(self.world.read())
                .facility(vehicle.facility_uid)
                .location_snapshot()
            )
        vehicle.validate_dispatch(
            contract.mode,
            contract.origin.city.city_uid,
            contract.tons,
        )
        fleet = self.market.candidates.resolve_fleet((vehicle,))
        if not self.market.candidates.eligible_ids(contract, fleet):
            raise ValueError("Transportklasse oder Fahrzeuggröße passt nicht.")

    def _build_trip(
        self,
        contract: ContractOffer,
        vehicle_id: str,
        quote: ContractQuote,
        departed_at: float,
    ) -> ActiveTransport:
        """Create the immutable dispatch snapshot used for tracking."""
        if quote.journey is None:
            raise ValueError("Dispatch requires a vehicle energy plan.")
        trip = ActiveTransport(
            id=str(uuid.uuid4()),
            vehicle_id=vehicle_id,
            contract=HistoricalContractSnapshot.from_offer(contract),
            origin=contract.origin,
            destination=contract.destination,
            route=quote.route,
            departed_at=departed_at,
            arrives_at=departed_at + quote.journey.duration_seconds,
            journey=quote.journey,
            dispatch_route=quote.dispatch_route,
            payout_eur=quote.economics.payout_eur,
            operating_cost_eur=quote.economics.operating_cost_eur,
        )
        return trip

    def _calculate_quote(
        self,
        contract: ContractOffer,
        route: DispatchRoutePlan,
        vehicle: OwnedVehicle,
    ) -> ContractQuote:
        """Revalidate vehicle eligibility before delegating quote planning."""
        self._validate_dispatch(vehicle, contract)
        return self.dispatch_planning.quote(
            contract, route, vehicle, self.time_scale
        )
