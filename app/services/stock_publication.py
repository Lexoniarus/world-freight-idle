"""Snapshot and publish stock against authoritative player and route facts."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle
from app.domain.market import MarketCandidate
from app.domain.market_preparation import (
    PreparationStatus,
    RelationDemandState,
    required_relations,
)
from app.domain.market_stock import (
    MarketArrival,
    MarketDemand,
    PreparedTemplate,
    TradeKey,
)
from app.domain.state_ports import GameUnitOfWork
from app.domain.world import WorldSnapshot
from app.services.market import MarketGenerator
from app.services.market_demand import MarketDemandResolver
from app.services.market_preparation import MarketPreparationService
from app.services.vehicle_coverage import trade_key

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StockSnapshot:
    """Keep short database reads separate from immutable planning inputs."""

    owned: tuple[OwnedVehicle, ...]
    offers: tuple[ContractOffer, ...]
    arrivals: tuple[MarketArrival, ...]
    status: PreparationStatus
    reference: WorldSnapshot
    demands: tuple[MarketDemand, ...]
    candidates: tuple[MarketCandidate, ...]
    ready: tuple[MarketCandidate, ...]
    templates: tuple[PreparedTemplate, ...]
    used: frozenset[str]
    bindings: dict[str, str]
    evidence: tuple[RelationDemandState, ...]
    observed_at: float
    ready_contexts: frozenset[tuple[TradeKey, str]]
    usable_offers: tuple[ContractOffer, ...]
    usable_templates: tuple[PreparedTemplate, ...]
    template_scopes: tuple[tuple[str, str], ...]
    phase_durations: tuple[tuple[str, float], ...]


@dataclass(slots=True)
class StockPublicationService:
    """Own fenced publication, leaving selection and routing elsewhere."""

    unit: GameUnitOfWork
    market: MarketGenerator
    preparation: MarketPreparationService
    demand: MarketDemandResolver
    guard: Callable[[], bool]

    def read(self) -> StockSnapshot:
        """Read one revision, then build candidates outside the writer."""
        prep = self.preparation
        stock = prep.stock
        assert stock is not None
        started = perf_counter()
        now = prep.clock()
        with self.unit.read_transaction():
            owned = self.unit.repository.list_vehicles()
            offers = self.unit.repository.list_offers()
            arrivals = stock.arrivals()
            status = prep.jobs.status(prep.user_id)
            used, bindings = stock.used(), stock.bindings()
        state_read = perf_counter()
        assert status is not None
        reference = self.market.candidates.reference()
        demands = self.demand.resolve(owned, arrivals, now)
        cities = tuple(sorted({d.vehicle.city_uid for d in demands}))
        scopes = tuple(
            sorted({(d.vehicle.city_uid, d.vehicle.model_id) for d in demands})
        )
        demand_read = perf_counter()
        templates = stock.scoped_templates(scopes)
        templates_read = perf_counter()
        candidates = self.market.candidates.build(
            cities,
            tuple(d.vehicle for d in demands),
        )
        candidates_built = perf_counter()
        pairs = required_relations(candidates)
        with prep.readiness.reading(pairs):
            ready = prep.ready_candidates(candidates)
            evidence = tuple(
                prep.demand_state(*pair) for pair in required_relations(ready)
            )
        readiness_read = perf_counter()
        return StockSnapshot(
            owned,
            offers,
            arrivals,
            status,
            reference,
            demands,
            candidates,
            ready,
            templates,
            used,
            bindings,
            evidence,
            now,
            frozenset(
                (trade_key(c), v.vehicle.vehicle_id)
                for c in ready
                for v in c.vehicles
            ),
            tuple(
                o
                for o in offers
                if o.is_available(now, self.market.model_id)
                and self.market.candidates.structurally_current(o)
            ),
            tuple(
                t
                for t in templates
                if t.offer.is_available(now, self.market.model_id)
                and self.market.candidates.structurally_current(t.offer)
            ),
            scopes,
            (
                ("state", (state_read - started) * 1000),
                ("demand", (demand_read - state_read) * 1000),
                ("templates", (templates_read - demand_read) * 1000),
                ("candidates", (candidates_built - templates_read) * 1000),
                ("readiness", (readiness_read - candidates_built) * 1000),
            ),
        )

    def unchanged(self, snapshot: StockSnapshot) -> bool:
        """Recheck inputs in the active publication transaction."""
        prep = self.preparation
        stock = prep.stock
        assert stock is not None
        return (
            self.guard()
            and self.unit.repository.list_vehicles() == snapshot.owned
            and self.unit.repository.list_offers() == snapshot.offers
            and stock.arrivals() == snapshot.arrivals
            and prep.jobs.status(prep.user_id) == snapshot.status
            and stock.used() == snapshot.used
            and stock.bindings() == snapshot.bindings
            and stock.scoped_templates(snapshot.template_scopes)
            == snapshot.templates
            and self.market.candidates.reference() == snapshot.reference
            and tuple(
                prep.demand_state(s.origin_uid, s.destination_uid)
                for s in snapshot.evidence
            )
            == snapshot.evidence
        )

    def publish(
        self,
        snapshot: StockSnapshot,
        templates: tuple[PreparedTemplate, ...],
        issued: tuple[tuple[str, ContractOffer], ...],
        active_contexts: tuple[str, ...] = (),
        completed_context: str | None = None,
    ) -> bool:
        """Commit new stock, private snapshots and diagnostics together."""
        prep = self.preparation
        stock = prep.stock
        assert stock is not None
        offers = snapshot.offers + tuple(offer for _, offer in issued)
        by_id = {offer.id: offer for offer in offers}
        coverage = tuple(
            self.market.vehicle_coverage.diagnose(
                d.vehicle,
                snapshot.candidates,
                snapshot.ready,
                snapshot.usable_offers + tuple(o for _, o in issued),
            )
            for d in snapshot.demands
            if not d.catalogue_only and d.transport_id is None
        )
        binding_pairs = tuple(
            dict.fromkeys(
                (
                    offer.origin.facility_uid,
                    offer.destination.facility_uid,
                )
                for offer in offers
                if self.market.candidates.structurally_current(offer)
            )
        )
        with prep.readiness.reading(binding_pairs):
            bindings = tuple(
                (offer.id, reference)
                for offer in offers
                if self.market.candidates.structurally_current(offer)
                and (
                    reference := prep.readiness.ready(
                        offer.origin.facility_uid,
                        offer.destination.facility_uid,
                    )
                )
                is not None
            )
        evidence_pairs = tuple(
            (state.origin_uid, state.destination_uid)
            for state in snapshot.evidence
        )
        all_pairs = tuple(dict.fromkeys((*binding_pairs, *evidence_pairs)))
        with self.unit.transaction(), prep.readiness.reading(all_pairs):
            if not self.unchanged(snapshot):
                return False
            # References outside current demand must also remain current.
            if any(
                prep.readiness.ready(
                    by_id[offer_id].origin.facility_uid,
                    by_id[offer_id].destination.facility_uid,
                )
                != ref
                for offer_id, ref in bindings
            ):
                return False
            for template in templates:
                stock.add(template)
            for template_id, offer in issued:
                stock.issue(template_id, offer)
            stock.reconcile_pending(active_contexts, completed_context)
            prep.references.replace(bindings)
            prep.jobs.publish_diagnostics(
                prep.user_id,
                snapshot.status.generation,
                coverage,
            )
        if templates or issued:
            LOGGER.info(
                "Prepared stock published",
                extra={
                    "event": "market.stock_published",
                    "data": {
                        "template_count": len(templates),
                        "personal_offer_count": len(issued),
                        "generation": snapshot.status.generation,
                    },
                },
            )
        return True
