"""Transactional lifecycle of one player's city markets."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle, VehicleCoverageDiagnostic
from app.domain.results import AvailableContract, MarketPresentation
from app.domain.state_ports import GameUnitOfWork
from app.services.market_components import MarketComponents
from app.services.market_scope import MarketScopeResolver
from app.services.market_selection import MarketSelectionService
from app.services.player_market_preparation import PlayerMarketPreparation
from app.services.player_market_routes import PlayerMarketRouteSnapshot

LOGGER = logging.getLogger(__name__)
RETAIN_MINIMUM_SECONDS = 60


@dataclass(slots=True)
class MarketLifecycleService:
    """Own refresh transactions and expose pruning within dispatch."""

    unit_of_work: GameUnitOfWork
    market: MarketComponents
    scope: MarketScopeResolver
    clock: Callable[[], float]
    preparation: PlayerMarketPreparation | None = None
    publication_guard: Callable[[], bool] | None = None
    selection: MarketSelectionService | None = None

    def published(self, *, refresh: bool = False) -> list[ContractOffer]:
        """Serve retained stock; only an explicit refresh writes demand."""
        if refresh and self.preparation is not None:
            self.preparation.request(changed=True)
        with self.unit_of_work.read_transaction():
            owned = self.unit_of_work.repository.list_vehicles()
            fleet = self.market.candidates.resolve_fleet(owned)
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
        if refresh and self.preparation is not None:
            self.preparation.request(changed=True)
        with self.unit_of_work.read_transaction():
            owned = self.unit_of_work.repository.list_vehicles()
            fleet = self.market.candidates.resolve_fleet(owned)
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
            if self.preparation is None:
                coverage = self._vehicle_diagnostics_in_transaction()
                status = None
            else:
                coverage = self.preparation.jobs.diagnostics(
                    self.preparation.user_id
                )
                status = self.preparation.jobs.status(self.preparation.user_id)
        return MarketPresentation(
            contracts,
            tuple(item for item in coverage if item.vehicle_id == vehicle_id),
            status,
        )

    def prune_in_transaction(self) -> None:
        """Prune within the caller's dispatch transaction, without refill."""
        if self.preparation is not None:
            self.preparation.request(changed=True)
            return
        owned = self.unit_of_work.repository.list_vehicles()
        cities = self.scope.resolve(owned)
        fleet = self.market.candidates.resolve_fleet(owned)
        self._store(self._retained(cities, fleet, self.clock()))

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
        routes: PlayerMarketRouteSnapshot | None,
    ) -> tuple[ContractOffer, ...]:
        """Filter stock using one previously loaded route snapshot."""
        candidates = self.market.candidates
        route_snapshot = cast(PlayerMarketRouteSnapshot, routes)
        if self.preparation is not None:
            assert route_snapshot is not None
        return tuple(
            offer
            for offer in offers
            if offer.is_available(now, self.market.model_id)
            and (
                offer.expires_at is None
                or offer.expires_at > now + RETAIN_MINIMUM_SECONDS
            )
            and offer.origin.city.city_uid in cities
            and candidates.eligible_ids(offer, fleet)
            and candidates.structurally_current(offer)
            and (
                self.preparation is None
                or self.preparation.routes.retained(offer, route_snapshot)
            )
        )

    def _store(self, offers: tuple[ContractOffer, ...]) -> None:
        """Persist changed offers inside the caller-owned transaction."""
        repository = self.unit_of_work.repository
        if offers != repository.list_offers():
            repository.replace_offers(offers)

    def refill_after_commit(self) -> None:
        """Keep a committed trip successful even when separate refill fails."""
        try:
            if self.preparation is not None:
                self.preparation.request(changed=True)
        except Exception:
            LOGGER.exception(
                "Post-commit market refill failed",
                extra={"event": "market.refill_failed"},
            )

    def present(
        self, offers: Sequence[ContractOffer], vehicle_id: str | None = None
    ) -> tuple[AvailableContract, ...]:
        """Attach transient eligibility and separate route references."""
        fleet = self.market.candidates.resolve_fleet(
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
        routes: PlayerMarketRouteSnapshot | None,
    ) -> tuple[AvailableContract, ...]:
        """Project contracts from one fleet and route snapshot."""
        result = []
        for offer in offers:
            eligible = self.market.candidates.eligible_ids(offer, fleet)
            reference = None
            if self.preparation is not None:
                assert routes is not None
                if not self.preparation.routes.retained(offer, routes):
                    continue
                eligible = self.preparation.routes.eligible(
                    offer,
                    fleet,
                    eligible,
                    routes,
                )
                reference = routes.offer_references.get(offer.id)
            if vehicle_id is None or vehicle_id in eligible:
                result.append(AvailableContract(offer, eligible, reference))
        if self.preparation is not None and self.preparation.stock is not None:
            assert self.selection is not None
            return self.selection.select(tuple(result), vehicle_id)
        return tuple(result)

    def _route_snapshot(
        self,
        offers: tuple[ContractOffer, ...],
        fleet: tuple[MarketVehicle, ...],
    ) -> PlayerMarketRouteSnapshot | None:
        """Load player route facts only when preparation is configured."""
        return (
            self.preparation.routes.read(offers, fleet)
            if self.preparation is not None
            else None
        )

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
        if self.preparation is not None:
            return self.preparation.jobs.diagnostics(self.preparation.user_id)
        with self.unit_of_work.read_transaction():
            return self._vehicle_diagnostics_in_transaction()

    def _vehicle_diagnostics_in_transaction(
        self,
    ) -> tuple[VehicleCoverageDiagnostic, ...]:
        """Project consistent cached evidence in the active transaction."""
        owned = self.unit_of_work.repository.list_vehicles()
        fleet = self.market.candidates.resolve_fleet(owned)
        candidates = self.market.candidates.build(
            self.scope.resolve(owned), fleet
        )
        ready = (
            self.preparation.ready_candidates(candidates)
            if self.preparation is not None
            else candidates
        )
        offers = self.unit_of_work.repository.list_offers()
        return tuple(
            self.market.vehicle_coverage.diagnose(
                vehicle, candidates, ready, offers
            )
            for vehicle in fleet
        )
