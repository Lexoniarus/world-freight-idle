"""Transactional lifecycle of one player's city markets."""

import logging
from collections.abc import Callable, Sequence
from contextlib import nullcontext
from dataclasses import asdict, dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle, VehicleCoverageDiagnostic
from app.domain.market_preparation import RelationDemandState
from app.domain.results import AvailableContract
from app.domain.state_ports import GameUnitOfWork
from app.services.market import MarketGenerator
from app.services.market_preparation import MarketPreparationService
from app.services.market_scope import MarketScopeResolver
from app.services.market_selection import MarketSelectionService

LOGGER = logging.getLogger(__name__)
RETAIN_MINIMUM_SECONDS = 60


@dataclass(slots=True)
class MarketLifecycleService:
    """Own refresh transactions and expose pruning within dispatch."""

    unit_of_work: GameUnitOfWork
    generator: MarketGenerator
    scope: MarketScopeResolver
    clock: Callable[[], float]
    preparation: MarketPreparationService | None = None
    publication_guard: Callable[[], bool] | None = None
    selection: MarketSelectionService | None = None

    def refresh(self, force: bool = False) -> list[ContractOffer]:
        """Plan outside the writer, then publish against unchanged inputs."""
        preparation = self.preparation
        if preparation is not None and preparation.stock is not None:
            return self.published(refresh=force)
        if preparation is not None:
            preparation.request()
        repository = self.unit_of_work.repository
        reference = self.generator.candidates.reference()
        with self.unit_of_work.read_transaction():
            owned = repository.list_vehicles()
            original_offers = repository.list_offers()
            status = (
                preparation.jobs.status(preparation.user_id)
                if preparation
                else None
            )
        cities = self.scope.resolve(owned)
        fleet = self.generator.candidates.resolve_fleet(owned)
        now = self.clock()
        retained = () if force else self._retained(cities, fleet, now)
        structural = self.generator.candidates.build(cities, fleet)
        ready = (
            preparation.ready_candidates(structural)
            if preparation
            else structural
        )
        offers, diagnostics = self.generator.generate(
            now, cities, fleet, retained, ready
        )
        coverage = tuple(
            self.generator.vehicle_coverage.diagnose(
                vehicle, structural, ready, offers
            )
            for vehicle in fleet
        )
        evidence = self._publication_evidence(offers, fleet)
        with self.unit_of_work.transaction():
            if (
                (self.publication_guard and not self.publication_guard())
                or repository.list_vehicles() != owned
                or repository.list_offers() != original_offers
                or self.generator.candidates.reference() != reference
                or self._publication_evidence(offers, fleet) != evidence
                or (
                    preparation
                    and preparation.jobs.status(preparation.user_id) != status
                )
            ):
                return list(repository.list_offers())
            self._store(offers)
            if preparation and status:
                preparation.jobs.publish_diagnostics(
                    preparation.user_id, status.generation, coverage
                )
            LOGGER.info(
                "City market refreshed",
                extra={
                    "event": "market.refresh",
                    "data": {
                        "active_city_count": len(cities),
                        "idle_vehicle_count": len(fleet),
                        "offer_count": len(offers),
                        "coverage": [asdict(d) for d in diagnostics],
                    },
                },
            )
            return list(offers)

    def _publication_evidence(
        self,
        offers: tuple[ContractOffer, ...],
        fleet: tuple[MarketVehicle, ...],
    ) -> tuple[RelationDemandState, ...]:
        """Fence provider, anchor and route revisions used by publication."""
        if self.preparation is None:
            return ()
        pairs = set()
        for offer in offers:
            origin = offer.origin.facility_uid
            pairs.add((origin, offer.destination.facility_uid))
            eligible = self.generator.candidates.eligible_ids(offer, fleet)
            pairs.update(
                (vehicle.facility_uid, origin)
                for vehicle in fleet
                if vehicle.vehicle_id in eligible
                and vehicle.facility_uid != origin
            )
        with self.preparation.readiness.reading():
            return tuple(
                self.preparation.demand_state(*pair) for pair in sorted(pairs)
            )

    def published(self, *, refresh: bool = False) -> list[ContractOffer]:
        """Serve usable publication and coalesce demand without generation."""
        if self.preparation is None:
            return self.refresh(force=refresh)
        self.preparation.request()
        with self.unit_of_work.read_transaction():
            owned = self.unit_of_work.repository.list_vehicles()
            fleet = self.generator.candidates.resolve_fleet(owned)
            offers = self.unit_of_work.repository.list_offers()
            retained = self._retained(
                self.scope.resolve(owned), fleet, self.clock()
            )
            status = self.preparation.jobs.status(self.preparation.user_id)
        missing = self.preparation.stock is None and len(retained) != len(
            offers
        )
        if (refresh or missing) and (
            status is not None and status.status != "partial"
        ):
            self.preparation.request(changed=True)
        return list(retained)

    def prune_in_transaction(self) -> None:
        """Prune within the caller's dispatch transaction, without refill."""
        if self.preparation is not None and self.preparation.stock is not None:
            self.preparation.request(changed=True)
            return
        owned = self.unit_of_work.repository.list_vehicles()
        cities = self.scope.resolve(owned)
        fleet = self.generator.candidates.resolve_fleet(owned)
        self._store(self._retained(cities, fleet, self.clock()))
        if self.preparation is not None:
            self.preparation.request(changed=True)

    def _retained(
        self,
        cities: tuple[str, ...],
        fleet: tuple[MarketVehicle, ...],
        now: float,
    ) -> tuple[ContractOffer, ...]:
        """Keep only fresh, structurally current, currently drivable offers."""
        with (
            self.preparation.readiness.reading()
            if self.preparation is not None
            else nullcontext()
        ):
            candidates = self.generator.candidates
            return tuple(
                offer
                for offer in self.unit_of_work.repository.list_offers()
                if offer.is_available(now, self.generator.model_id)
                and (
                    offer.expires_at is None
                    or offer.expires_at > now + RETAIN_MINIMUM_SECONDS
                )
                and offer.origin.city.city_uid in cities
                and candidates.eligible_ids(offer, fleet)
                and candidates.structurally_current(offer)
                and (
                    self.preparation is None
                    or self.preparation.retained(offer)
                )
            )

    def _store(self, offers: tuple[ContractOffer, ...]) -> None:
        """Persist changed offers inside the caller-owned transaction."""
        with (
            self.preparation.readiness.reading()
            if self.preparation is not None
            else nullcontext()
        ):
            repository = self.unit_of_work.repository
            if offers != repository.list_offers():
                repository.replace_offers(offers)
            if self.preparation is not None:
                self.preparation.bind(offers)

    def refill_after_commit(self) -> None:
        """Keep a committed trip successful even when separate refill fails."""
        try:
            if self.preparation is None:
                self.refresh()
            else:
                self.preparation.request()
        except Exception:
            LOGGER.exception(
                "Post-commit market refill failed",
                extra={"event": "market.refill_failed"},
            )

    def present(
        self, offers: Sequence[ContractOffer], vehicle_id: str | None = None
    ) -> tuple[AvailableContract, ...]:
        """Attach transient eligibility and separate route references."""
        with (
            self.preparation.readiness.reading()
            if self.preparation is not None
            else nullcontext()
        ):
            fleet = self.generator.candidates.resolve_fleet(
                self.unit_of_work.repository.list_vehicles()
            )
            if vehicle_id is not None and not any(
                v.vehicle_id == vehicle_id for v in fleet
            ):
                raise ValueError(
                    "Eigenes einsatzbereites Fahrzeug erforderlich."
                )
            result = []
            for offer in offers:
                eligible = self.generator.candidates.eligible_ids(offer, fleet)
                reference = None
                if self.preparation is not None:
                    if not self.preparation.retained(offer):
                        continue
                    eligible = self.preparation.eligible(
                        offer, fleet, eligible
                    )
                    reference = self.preparation.references.get(offer.id)
                if vehicle_id is None or vehicle_id in eligible:
                    result.append(
                        AvailableContract(offer, eligible, reference)
                    )
            if (
                self.preparation is not None
                and self.preparation.stock is not None
            ):
                assert self.selection is not None
                return self.selection.select(tuple(result), vehicle_id)
            return tuple(result)

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
        fleet = self.generator.candidates.resolve_fleet(owned)
        candidates = self.generator.candidates.build(
            self.scope.resolve(owned), fleet
        )
        ready = (
            self.preparation.ready_candidates(candidates)
            if self.preparation is not None
            else candidates
        )
        offers = self.unit_of_work.repository.list_offers()
        return tuple(
            self.generator.vehicle_coverage.diagnose(
                vehicle, candidates, ready, offers
            )
            for vehicle in fleet
        )
