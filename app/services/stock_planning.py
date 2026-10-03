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
from app.services.deterministic_market_random import (
    DeterministicMarketRandom,
)
from app.services.market_coverage import CityCoverage
from app.services.vehicle_coverage import (
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
        templates: tuple[PreparedTemplate, ...],
        used: frozenset[str] = frozenset(),
    ) -> tuple[StockTarget, ...]:
        """Count actual compatible offers, or shared catalogue-only supply."""
        by_vehicle: dict[str, list[MarketCandidate]] = defaultdict(list)
        ready_by_vehicle: dict[str, list[MarketCandidate]] = defaultdict(list)
        offers_by_city: dict[str, list[ContractOffer]] = defaultdict(list)
        templates_by_model: dict[tuple[str, str], list[ContractOffer]] = (
            defaultdict(list)
        )
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
        active_models: dict[tuple[str, str], int] = {}
        for demand in demands:
            if not demand.catalogue_only:
                key = (demand.vehicle.city_uid, demand.vehicle.model_id)
                active_models[key] = min(
                    active_models.get(key, 4),
                    3 if demand.transport_id else 2,
                )
        for template in templates:
            if (
                template.city_uid,
                template.model_id,
            ) in active_models and template.template_id in used:
                continue
            templates_by_model[template.city_uid, template.model_id].append(
                template.offer
            )
        result = []
        for demand in demands:
            vehicle = demand.vehicle
            pool = tuple(by_vehicle[vehicle.vehicle_id])
            retained = (
                templates_by_model[vehicle.city_uid, vehicle.model_id]
                if demand.catalogue_only
                else offers_by_city[vehicle.city_uid]
            )
            eligible = vehicle_offers(
                tuple(retained),
                vehicle,
                tuple(ready_by_vehicle[vehicle.vehicle_id]),
            )
            for band in DISTANCE_BANDS:
                choices = tuple(
                    c for c in pool if c.distance_profile.distance_band == band
                )
                count = sum(
                    o.market_context is not None
                    and o.market_context.distance_band == band
                    for o in eligible
                )
                if not choices or count >= self.policy.reserve_per_band:
                    continue
                priority = (
                    active_models.get((vehicle.city_uid, vehicle.model_id), 4)
                    if demand.catalogue_only
                    else (1 if demand.transport_id else 0)
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
        """Return the least represented relation/cargo/destination rank."""
        coverage = CityCoverage()
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
            coverage.record(
                offer.origin.facility_uid,
                offer.destination.facility_uid,
                offer.cargo.nhm_row_id,
                offer.destination.city.city_uid,
                context.distance_band,
            )
        preferred_rank = min(coverage.rank(c) for c in target.choices)
        ranked = tuple(
            c for c in target.choices if coverage.rank(c) == preferred_rank
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
