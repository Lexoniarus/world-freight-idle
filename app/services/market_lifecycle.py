"""Transactional lifecycle of one player's city markets."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle
from app.domain.results import AvailableContract
from app.domain.state_ports import GameUnitOfWork
from app.services.market import MarketGenerator
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

    def refresh(self, force: bool = False) -> list[ContractOffer]:
        """Read fleet, retain valid work and fill coverage atomically."""
        with self.unit_of_work.transaction():
            repository = self.unit_of_work.repository
            owned = repository.list_vehicles()
            cities = self.scope.resolve(owned)
            fleet = self.generator.candidates.resolve_fleet(owned)
            now = self.clock()
            retained = () if force else self._retained(cities, fleet, now)
            offers, diagnostics = self.generator.generate(
                now, cities, fleet, retained
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
        )

    def _store(self, offers: tuple[ContractOffer, ...]) -> None:
        """Persist changed offers inside the caller-owned transaction."""
        repository = self.unit_of_work.repository
        if offers != repository.list_offers():
            repository.replace_offers(offers)

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
        self, offers: Sequence[ContractOffer]
    ) -> tuple[AvailableContract, ...]:
        """Attach transient eligibility without changing offer snapshots."""
        fleet = self.generator.candidates.resolve_fleet(
            self.unit_of_work.repository.list_vehicles()
        )
        return tuple(
            AvailableContract(
                offer, self.generator.candidates.eligible_ids(offer, fleet)
            )
            for offer in offers
        )
