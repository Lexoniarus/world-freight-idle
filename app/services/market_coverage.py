"""Plan facility and distance coverage without materializing offers."""

import random
from collections import Counter
from dataclasses import dataclass, field

from app.domain.contracts import ContractOffer
from app.domain.market import CoverageDiagnostic, CoveragePlan, MarketCandidate
from app.domain.market_profiles import DISTANCE_BANDS

MINIMUM_DISTANCE_OFFERS = 3


@dataclass(slots=True)
class CityCoverage:
    """Track retained and planned coverage within a single city plan."""

    facilities: Counter[str] = field(default_factory=Counter)
    bands: Counter[str] = field(default_factory=Counter)
    relations: Counter[tuple[str, str, int]] = field(default_factory=Counter)
    cargo: Counter[int] = field(default_factory=Counter)
    destinations: Counter[str] = field(default_factory=Counter)

    def record(
        self,
        origin: str,
        destination: str,
        cargo: int,
        destination_city: str,
        band: str,
    ) -> None:
        """Count one retained or planned offer using the same dimensions."""
        self.facilities[origin] += 1
        self.bands[band] += 1
        self.relations[origin, destination, cargo] += 1
        self.cargo[cargo] += 1
        self.destinations[destination_city] += 1

    def rank(self, candidate: MarketCandidate) -> tuple[int, int, int]:
        """Prefer unused relations, cargo nodes, then destination cities."""
        trade = candidate.trade
        return (
            self.relations[
                trade.origin.facility_uid,
                trade.destination.facility_uid,
                trade.cargo.nhm_row_id,
            ],
            self.cargo[trade.cargo.nhm_row_id],
            self.destinations[trade.destination.address.city.city_uid],
        )

    def add_candidate(self, candidate: MarketCandidate) -> None:
        """Count planned coverage before the factory creates an offer."""
        trade = candidate.trade
        self.record(
            trade.origin.facility_uid,
            trade.destination.facility_uid,
            trade.cargo.nhm_row_id,
            trade.destination.address.city.city_uid,
            candidate.distance_profile.distance_band,
        )


@dataclass(slots=True)
class MarketCoverageService:
    """Select only missing city coverage using an injected random source."""

    rng: random.Random

    def plan(
        self,
        cities: tuple[str, ...],
        candidates: tuple[MarketCandidate, ...],
        retained: tuple[ContractOffer, ...],
    ) -> CoveragePlan:
        """Compose independent city plans and compact coverage diagnostics."""
        selected: list[MarketCandidate] = []
        diagnostics = []
        for city in cities:
            pool = tuple(
                c
                for c in candidates
                if c.trade.origin.address.city.city_uid == city
            )
            existing = tuple(
                o for o in retained if o.origin.city.city_uid == city
            )
            planned, diagnostic = self._plan_city(city, pool, existing)
            selected.extend(planned)
            diagnostics.append(diagnostic)
        return CoveragePlan(tuple(selected), tuple(diagnostics))

    def _plan_city(
        self,
        city: str,
        pool: tuple[MarketCandidate, ...],
        retained: tuple[ContractOffer, ...],
    ) -> tuple[tuple[MarketCandidate, ...], CoverageDiagnostic]:
        """Apply facility coverage first and then fill available bands."""
        coverage = CityCoverage()
        for offer in retained:
            assert offer.market_context is not None
            coverage.record(
                offer.origin.facility_uid,
                offer.destination.facility_uid,
                offer.cargo.nhm_row_id,
                offer.destination.city.city_uid,
                offer.market_context.distance_band,
            )
        selected: list[MarketCandidate] = []
        origins = sorted({c.trade.origin.facility_uid for c in pool})
        for origin in origins:
            if not coverage.facilities[origin]:
                subset = tuple(
                    c for c in pool if c.trade.origin.facility_uid == origin
                )
                selected.append(self._select(subset, coverage))
        for band in DISTANCE_BANDS:
            subset = tuple(
                c for c in pool if c.distance_profile.distance_band == band
            )
            while subset and coverage.bands[band] < MINIMUM_DISTANCE_OFFERS:
                selected.append(self._select(subset, coverage))
        diagnostic = CoverageDiagnostic(
            city,
            len(origins),
            sum(coverage.facilities[o] > 0 for o in origins),
            (
                coverage.bands["short"],
                coverage.bands["medium"],
                coverage.bands["long"],
            ),
            tuple(
                b
                for b in DISTANCE_BANDS
                if coverage.bands[b] < MINIMUM_DISTANCE_OFFERS
            ),
        )
        return tuple(selected), diagnostic

    def _select(
        self,
        pool: tuple[MarketCandidate, ...],
        coverage: CityCoverage,
    ) -> MarketCandidate:
        """Choose by diversity rank then candidate weight and record it."""
        rank = min(coverage.rank(c) for c in pool)
        preferred = tuple(c for c in pool if coverage.rank(c) == rank)
        candidate = self.rng.choices(
            preferred, weights=[c.weight for c in preferred], k=1
        )[0]
        coverage.add_candidate(candidate)
        return candidate
