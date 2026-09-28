"""Materialize reusable trade seeds and immutable private offer terms."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate
from app.domain.market_stock import PreparedTemplate, StockPolicy
from app.services.contract_factory import ContractFactory
from app.services.stock_planning import StockTarget
from app.services.vehicle_coverage import trade_key


@dataclass(slots=True)
class MarketTemplateService:
    """Own generation, independently of scheduling, HTTP and persistence."""

    factory: ContractFactory
    policy: StockPolicy
    clock: Callable[[], float]

    def materialize(
        self,
        templates: tuple[PreparedTemplate, ...],
        used: frozenset[str],
        bindings: dict[str, str],
        target: StockTarget,
        candidate: MarketCandidate,
    ) -> tuple[
        tuple[PreparedTemplate, ...], tuple[tuple[str, ContractOffer], ...]
    ]:
        """Fill a bounded deficit, reusing supply before creating new seeds."""
        limit = (
            self.policy.visible_per_band
            if target.priority < 2
            else self.policy.reserve_per_band
        )
        deficit = limit - target.count
        reusable = tuple(
            t
            for t in templates
            if t.model_id == target.demand.vehicle.model_id
            and t.template_id not in used
            and t.template_id not in bindings
            and (
                t.offer.origin.facility_uid,
                t.offer.destination.facility_uid,
                t.offer.cargo.nhm_row_id,
            )
            == trade_key(candidate)
        )
        created: list[PreparedTemplate] = []
        issued = []
        for index in range(deficit):
            if not target.demand.catalogue_only and index < len(reusable):
                template = reusable[index]
            else:
                template = PreparedTemplate(
                    uuid4().hex,
                    target.demand.vehicle.model_id,
                    target.demand.vehicle.city_uid,
                    ContractOffer.from_snapshot(
                        self.factory.build(candidate, self.clock())
                    ),
                )
                created.append(template)
            if not target.demand.catalogue_only:
                offer = ContractOffer.from_snapshot(
                    self.factory.build(candidate, self.clock())
                )
                issued.append((template.template_id, offer))
        return tuple(created), tuple(issued)
