"""Prioritize finite market deficits independently of provider execution."""

from collections import defaultdict
from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate
from app.domain.market_profiles import DISTANCE_BANDS
from app.domain.market_stock import (
    MarketDemand,
    PreparedTemplate,
    StockPolicy,
    TradeKey,
)
from app.services.market.diversity import MarketDiversity
from app.services.market.randomness import (
    DeterministicMarketRandom,
)
from app.services.market.vehicle_coverage import (
    restrict_candidate,
    trade_key,
    vehicle_offers,
)


@dataclass(frozen=True, slots=True)
class StockTarget:
    """Identify one fair scheduling unit with its already available count."""

    demand: MarketDemand
    band: str
    count: int
    priority: int
    choices: tuple[MarketCandidate, ...]
    total_available: int = 0
    offers: tuple[ContractOffer, ...] = ()

    @property
    def key(self) -> str:
        """Use identities, not unstable iteration positions, for rotation."""
        vehicle = self.demand.vehicle
        return ":".join(
            (
                vehicle.vehicle_id,
                vehicle.city_uid,
                vehicle.facility_uid,
                self.band,
            )
        )


@dataclass(frozen=True, slots=True)
class StockPlanningService:
    """Rank real deficits, preserving deterministic fair group rotation."""

    policy: StockPolicy
    random: DeterministicMarketRandom = DeterministicMarketRandom()

    def targets(
        self,
        demands: tuple[MarketDemand, ...],
        candidates: tuple[MarketCandidate, ...],
        ready: tuple[MarketCandidate, ...],
        offers: tuple[ContractOffer, ...],
    ) -> tuple[StockTarget, ...]:
        """Count actual compatible offers for concrete vehicle demand."""
        by_vehicle: dict[str, list[MarketCandidate]] = defaultdict(list)
        ready_by_vehicle: dict[str, list[MarketCandidate]] = defaultdict(list)
        offers_by_city: dict[str, list[ContractOffer]] = defaultdict(list)
        for candidate in candidates:
            for compatible in candidate.vehicles:
                by_vehicle[compatible.vehicle.vehicle_id].append(
                    restrict_candidate(candidate, (compatible,))
                )
        for candidate in ready:
            for compatible in candidate.vehicles:
                ready_by_vehicle[compatible.vehicle.vehicle_id].append(
                    candidate
                )
        for offer in offers:
            offers_by_city[offer.origin.city.city_uid].append(offer)
        result = []
        for demand in demands:
            vehicle = demand.vehicle
            pool = tuple(by_vehicle[vehicle.vehicle_id])
            eligible = vehicle_offers(
                tuple(offers_by_city[vehicle.city_uid]),
                vehicle,
                tuple(ready_by_vehicle[vehicle.vehicle_id]),
            )
            for band in DISTANCE_BANDS:
                band_offers = tuple(
                    offer
                    for offer in eligible
                    if offer.market_context is not None
                    and offer.market_context.distance_band == band
                )
                choices = tuple(
                    c for c in pool if c.distance_profile.distance_band == band
                )
                count = len(band_offers)
                if not choices or count >= self.policy.reserve_per_band:
                    continue
                priority = (
                    (1 if demand.transport_id else 0)
                    if count < self.policy.visible_per_band
                    else (3 if demand.transport_id else 2)
                )
                result.append(
                    StockTarget(
                        demand,
                        band,
                        count,
                        priority,
                        choices,
                        len(eligible),
                        band_offers,
                    )
                )
        return tuple(result)

    def order(
        self,
        targets: tuple[StockTarget, ...],
        cursor: str,
    ) -> tuple[StockTarget, ...]:
        """Serve urgent tiers first and rotate equal-priority contexts."""
        return tuple(
            sorted(
                targets,
                key=lambda target: (
                    target.priority,
                    target.total_available > 0
                    if target.priority < 2
                    else False,
                    target.demand.available_at
                    if target.demand.transport_id
                    else 0,
                    target.key <= cursor,
                    target.key,
                ),
            )
        )

    def choose(
        self,
        target: StockTarget,
        pending: TradeKey | None,
        templates: tuple[PreparedTemplate, ...],
    ) -> MarketCandidate:
        """Resume partial work; otherwise prefer underrepresented trades."""
        existing = next(
            (c for c in target.choices if trade_key(c) == pending),
            None,
        )
        if existing is not None:
            return existing
        preferred = self.preferred(target, templates)
        identities = tuple(
            "\x1e".join(map(str, trade_key(candidate)))
            for candidate in preferred
        )
        index = self.random.weighted_index(
            identities,
            tuple(candidate.weight for candidate in preferred),
            target.key,
            target.priority,
            target.count,
            "candidate",
        )
        return preferred[index]

    def preferred(
        self,
        target: StockTarget,
        templates: tuple[PreparedTemplate, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Prefer personal diversity, then shared template diversity."""
        personal = MarketDiversity()
        for offer in target.offers:
            personal.record_offer(offer)
        personal_rank = min(personal.rank(c) for c in target.choices)
        personal_choices = tuple(
            candidate
            for candidate in target.choices
            if personal.rank(candidate) == personal_rank
        )
        shared = MarketDiversity()
        for template in templates:
            offer = template.offer
            context = offer.market_context
            if (
                template.city_uid != target.demand.vehicle.city_uid
                or template.model_id != target.demand.vehicle.model_id
                or context is None
                or context.distance_band != target.band
            ):
                continue
            shared.record(
                offer.origin.facility_uid,
                offer.destination.facility_uid,
                offer.cargo.nhm_row_id,
                offer.destination.city.city_uid,
            )
        preferred_rank = min(shared.rank(c) for c in personal_choices)
        ranked = tuple(
            candidate
            for candidate in personal_choices
            if shared.rank(candidate) == preferred_rank
        )
        unique: dict[TradeKey, MarketCandidate] = {}
        for candidate in ranked:
            key = trade_key(candidate)
            current = unique.get(key)
            if current is None or (candidate.weight, repr(candidate)) > (
                current.weight,
                repr(current),
            ):
                unique[key] = candidate
        return tuple(unique[key] for key in sorted(unique))
