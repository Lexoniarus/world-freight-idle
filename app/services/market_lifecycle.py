"""Transactional lifecycle of one player's city markets."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle, VehicleCoverageDiagnostic
from app.domain.results import AvailableContract
from app.domain.state_ports import GameUnitOfWork
from app.services.market import MarketGenerator
from app.services.market_preparation import MarketPreparationService
from app.services.market_scope import MarketScopeResolver

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

    def refresh(self, force: bool = False) -> list[ContractOffer]:
        """Read fleet, retain valid work and fill coverage atomically."""
        with self.unit_of_work.transaction():
            repository = self.unit_of_work.repository
            owned = repository.list_vehicles()
            cities = self.scope.resolve(owned)
            fleet = self.generator.candidates.resolve_fleet(owned)
            now = self.clock()
            retained = () if force else self._retained(cities, fleet, now)
            prepared = None
            if self.preparation is not None:
                prepared = self.preparation.prepare_publication(
                    self.generator.candidates.build(cities, fleet), fleet
                )
            offers, diagnostics = self.generator.generate(
                now, cities, fleet, retained, prepared
            )
            self._store(offers)
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

    def prune_in_transaction(self) -> None:
        """Prune within the caller's dispatch transaction, without refill."""
        owned = self.unit_of_work.repository.list_vehicles()
        cities = self.scope.resolve(owned)
        fleet = self.generator.candidates.resolve_fleet(owned)
        self._store(self._retained(cities, fleet, self.clock()))

    def _retained(
        self,
        cities: tuple[str, ...],
        fleet: tuple[MarketVehicle, ...],
        now: float,
    ) -> tuple[ContractOffer, ...]:
        """Keep only fresh, structurally current, currently drivable offers."""
        candidates = self.generator.candidates
        return tuple(
            offer
            for offer in self.unit_of_work.repository.list_offers()
            if offer.is_available(now, self.generator.model_id)
            and offer.expires_at > now + RETAIN_MINIMUM_SECONDS
            and offer.origin.city.city_uid in cities
            and candidates.eligible_ids(offer, fleet)
            and candidates.structurally_current(offer)
            and (self.preparation is None or self.preparation.retained(offer))
        )

    def _store(self, offers: tuple[ContractOffer, ...]) -> None:
        """Persist changed offers inside the caller-owned transaction."""
        repository = self.unit_of_work.repository
        if offers != repository.list_offers():
            repository.replace_offers(offers)
        if self.preparation is not None:
            self.preparation.bind(offers)

    def refill_after_commit(self) -> None:
        """Keep a committed trip successful even when separate refill fails."""
        try:
            self.refresh()
        except Exception:
            LOGGER.exception(
                "Post-commit market refill failed",
                extra={"event": "market.refill_failed"},
            )

    def present(
        self, offers: Sequence[ContractOffer], vehicle_id: str | None = None
    ) -> tuple[AvailableContract, ...]:
        """Attach transient eligibility and separate route references."""
        fleet = self.generator.candidates.resolve_fleet(
            self.unit_of_work.repository.list_vehicles()
        )
        if vehicle_id is not None and not any(
            v.vehicle_id == vehicle_id for v in fleet
        ):
            raise ValueError("Eigenes einsatzbereites Fahrzeug erforderlich.")
        result = []
        for offer in offers:
            eligible = self.generator.candidates.eligible_ids(offer, fleet)
            reference = None
            if self.preparation is not None:
                if not self.preparation.retained(offer):
                    continue
                eligible = self.preparation.eligible(offer, fleet, eligible)
                reference = self.preparation.references.get(offer.id)
            if vehicle_id is None or vehicle_id in eligible:
                result.append(AvailableContract(offer, eligible, reference))
        return tuple(result)

    def vehicle_diagnostics(self) -> tuple[VehicleCoverageDiagnostic, ...]:
        """Read actual vehicle coverage without scheduling provider work."""
        with self.unit_of_work.transaction():
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
