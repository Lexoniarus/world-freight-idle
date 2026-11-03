"""Transactional lifecycle of one player's city markets."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle, VehicleCoverageDiagnostic
from app.domain.results import AvailableContract, MarketPresentation
from app.domain.state_ports import GameUnitOfWork
from app.services.market.contract_factory import ContractFactory
from app.services.market.generation_services import MarketGenerationServices
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import (
    PlayerMarketRouteService,
    PlayerMarketRouteSnapshot,
)
from app.services.market.player_stores import PlayerMarketStores
from app.services.market.scope import MarketScopeResolver
from app.services.market.selection import MarketSelectionService

RETAIN_MINIMUM_SECONDS = 60


@dataclass(slots=True)
class MarketLifecycleService:
    """Own refresh transactions and expose pruning within dispatch."""

    unit_of_work: GameUnitOfWork
    generation: MarketGenerationServices
    scope: MarketScopeResolver
    clock: Callable[[], float]
    demand: PlayerMarketDemandService
    routes: PlayerMarketRouteService
    stores: PlayerMarketStores
    selection: MarketSelectionService

    def published(self, *, refresh: bool = False) -> list[ContractOffer]:
        """Serve retained stock; only an explicit refresh writes demand."""
        if refresh:
            self.demand.invalidate()
        with self.unit_of_work.read_transaction():
            owned = self.unit_of_work.repository.list_vehicles()
            fleet = self.generation.candidates.resolve_fleet(owned)
            retained = self._retained(
                self.scope.resolve(owned), fleet, self.clock()
            )
        return list(retained)

    def read_market(
        self,
        vehicle_id: str,
        *,
        refresh: bool = False,
    ) -> MarketPresentation:
        """Read one authorized vehicle market without duplicate projections."""
        if refresh:
            self.demand.invalidate()
        with self.unit_of_work.read_transaction():
            owned = self.unit_of_work.repository.list_vehicles()
            fleet = self.generation.candidates.resolve_fleet(owned)
            self._require_vehicle(fleet, vehicle_id)
            cities = self.scope.resolve(owned)
            now = self.clock()
            stored = self.unit_of_work.repository.list_offers()
            routes = self._route_snapshot(stored, fleet)
            retained = self._retained_from(
                stored,
                cities,
                fleet,
                now,
                routes,
            )
            contracts = self._present_from(
                retained,
                fleet,
                vehicle_id,
                routes,
            )
            coverage = self.demand.diagnostics()
            status = self.demand.status()
        return MarketPresentation(
            contracts,
            tuple(item for item in coverage if item.vehicle_id == vehicle_id),
            status,
        )

    def _retained(
        self,
        cities: tuple[str, ...],
        fleet: tuple[MarketVehicle, ...],
        now: float,
    ) -> tuple[ContractOffer, ...]:
        """Keep only fresh, structurally current, currently drivable offers."""
        offers = self.unit_of_work.repository.list_offers()
        routes = self._route_snapshot(offers, fleet)
        return self._retained_from(offers, cities, fleet, now, routes)

    def _retained_from(
        self,
        offers: tuple[ContractOffer, ...],
        cities: tuple[str, ...],
        fleet: tuple[MarketVehicle, ...],
        now: float,
        routes: PlayerMarketRouteSnapshot,
    ) -> tuple[ContractOffer, ...]:
        """Filter stock using one previously loaded route snapshot."""
        candidates = self.generation.candidates
        return tuple(
            offer
            for offer in offers
            if offer.is_available(now, ContractFactory.model_id)
            and (
                offer.expires_at is None
                or offer.expires_at > now + RETAIN_MINIMUM_SECONDS
            )
            and offer.origin.city.city_uid in cities
            and candidates.eligible_ids(offer, fleet)
            and candidates.structurally_current(offer)
            and self.routes.matches_snapshot(offer, routes)
        )

    def present(
        self, offers: Sequence[ContractOffer], vehicle_id: str | None = None
    ) -> tuple[AvailableContract, ...]:
        """Attach transient eligibility and separate route references."""
        fleet = self.generation.candidates.resolve_fleet(
            self.unit_of_work.repository.list_vehicles()
        )
        self._require_vehicle(fleet, vehicle_id)
        offer_tuple = tuple(offers)
        routes = self._route_snapshot(offer_tuple, fleet)
        return self._present_from(offer_tuple, fleet, vehicle_id, routes)

    def _present_from(
        self,
        offers: tuple[ContractOffer, ...],
        fleet: tuple[MarketVehicle, ...],
        vehicle_id: str | None,
        routes: PlayerMarketRouteSnapshot,
    ) -> tuple[AvailableContract, ...]:
        """Project contracts from one fleet and route snapshot."""
        result = []
        for offer in offers:
            eligible = self.generation.candidates.eligible_ids(offer, fleet)
            if not self.routes.matches_snapshot(offer, routes):
                continue
            eligible = self.routes.eligible_from_snapshot(
                offer,
                fleet,
                eligible,
                routes,
            )
            reference = routes.offer_references.get(offer.id)
            if vehicle_id is None or vehicle_id in eligible:
                result.append(AvailableContract(offer, eligible, reference))
        return self.selection.select(tuple(result), vehicle_id)

    def _route_snapshot(
        self,
        offers: tuple[ContractOffer, ...],
        fleet: tuple[MarketVehicle, ...],
    ) -> PlayerMarketRouteSnapshot:
        """Load all player route facts for one market projection."""
        return self.routes.read(offers, fleet)

    def _require_vehicle(
        self,
        fleet: tuple[MarketVehicle, ...],
        vehicle_id: str | None,
    ) -> None:
        """Reject a scoped market without an owned idle vehicle."""
        if vehicle_id is not None and not any(
            item.vehicle_id == vehicle_id for item in fleet
        ):
            raise ValueError("Eigenes einsatzbereites Fahrzeug erforderlich.")

    def vehicle_diagnostics(self) -> tuple[VehicleCoverageDiagnostic, ...]:
        """Read actual vehicle coverage without scheduling provider work."""
        return self.demand.diagnostics()
