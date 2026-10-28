"""Quote and dispatch contracts against prepared routes."""

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.game import OwnedVehicle
from app.domain.results import ContractQuote
from app.domain.routes import DispatchRoutePlan
from app.domain.state_ports import GameUnitOfWork
from app.domain.transports import ActiveTransport
from app.services.dispatch_eligibility import DispatchEligibilityService
from app.services.dispatch_planning import DispatchPlanningService
from app.services.market_components import MarketComponents
from app.services.player_market_stock import PlayerMarketStockContext
from app.services.transport_settlement import TransportSettlementService
from app.services.vehicle_location import VehicleLocationResolver

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TransportDispatchService:
    """Own quote validation and atomic transport creation."""

    unit: GameUnitOfWork
    market: MarketComponents
    planning: DispatchPlanningService
    eligibility: DispatchEligibilityService
    vehicle_locations: VehicleLocationResolver
    settlement: TransportSettlementService
    clock: Callable[[], float]
    time_scale: float
    prune_market: Callable[[], None]
    refill_market: Callable[[], None]
    stock: PlayerMarketStockContext | None = None

    async def quote_contract(
        self, contract_id: str, vehicle_id: str
    ) -> ContractQuote:
        """Load prepared routes and quote one selected vehicle."""
        self.settlement.reconcile()
        contract = self.find_contract(contract_id)
        vehicle = self.find_vehicle(
            self.unit.repository.list_vehicles(),
            vehicle_id,
        )
        self.validate_dispatch(vehicle, contract)
        assert vehicle.location is not None
        route = await self.planning.route(vehicle.location, contract)
        if self.find_contract(contract_id) != contract:
            raise ValueError("Auftrag wurde während der Kalkulation geändert.")
        vehicle = self.find_vehicle(
            self.unit.repository.list_vehicles(),
            vehicle_id,
        )
        quote = self.calculate_quote(contract, route, vehicle)
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
        """Quote once, then atomically reserve vehicle, funds and offer."""
        quote = await self.quote_contract(contract_id, vehicle_id)
        with self.unit.transaction():
            trip = self.commit_dispatch(contract_id, vehicle_id, quote)
        self.refill_market()
        return trip

    def commit_dispatch(
        self,
        contract_id: str,
        vehicle_id: str,
        quote: ContractQuote,
    ) -> ActiveTransport:
        """Revalidate and atomically reserve the truck and funds."""
        repository = self.unit.repository
        contract = self.find_contract(contract_id)
        if contract != quote.contract:
            raise ValueError("Auftrag wurde während der Kalkulation geändert.")
        vehicle = self.find_vehicle(repository.list_vehicles(), vehicle_id)
        self.validate_dispatch(vehicle, contract)
        if quote.dispatch_route is None:
            raise ValueError("Dispatch requires a routed departure plan.")
        quote = self.calculate_quote(contract, quote.dispatch_route, vehicle)
        player = self.settlement.player_state()
        player.debit(quote.economics.operating_cost_eur)
        trip = self.build_trip(contract, vehicle_id, quote, self.clock())
        vehicle.start_trip()
        repository.save_player(player)
        repository.save_vehicle(vehicle)
        repository.save_transport(trip)
        if self.stock is not None:
            self.stock.stock.consume(contract_id, self.clock())
        repository.remove_offer(contract_id)
        self.prune_market()
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

    def find_contract(self, contract_id: str) -> ContractOffer:
        """Find one current offer using the injected clock."""
        now = self.clock()
        contract = next(
            (
                offer
                for offer in self.unit.repository.list_offers()
                if offer.id == contract_id
                and offer.is_available(now, self.market.model_id)
            ),
            None,
        )
        if contract is None:
            raise KeyError("Auftrag nicht gefunden")
        return contract

    def find_vehicle(
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

    def validate_dispatch(
        self,
        vehicle: OwnedVehicle,
        contract: ContractOffer,
    ) -> None:
        """Resolve location and enforce pure dispatch eligibility."""
        self.vehicle_locations.resolve(vehicle)
        self.eligibility.require_eligible(vehicle, contract)

    def build_trip(
        self,
        contract: ContractOffer,
        vehicle_id: str,
        quote: ContractQuote,
        departed_at: float,
    ) -> ActiveTransport:
        """Create the immutable dispatch snapshot used for tracking."""
        if quote.journey is None:
            raise ValueError("Dispatch requires a vehicle energy plan.")
        return ActiveTransport(
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
            cost_breakdown=quote.economics.cost_breakdown,
            payout_eur=quote.economics.payout_eur,
            operating_cost_eur=quote.economics.operating_cost_eur,
        )

    def calculate_quote(
        self,
        contract: ContractOffer,
        route: DispatchRoutePlan,
        vehicle: OwnedVehicle,
    ) -> ContractQuote:
        """Revalidate eligibility before delegating deterministic pricing."""
        self.validate_dispatch(vehicle, contract)
        return self.planning.quote(
            contract,
            route,
            vehicle,
            self.time_scale,
        )
