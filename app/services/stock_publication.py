"""Snapshot and publish stock against authoritative player and route facts."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle
from app.domain.market import MarketCandidate, VehicleCoverageDiagnostic
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
from app.domain.routing_readiness import RouteReference
from app.domain.state_ports import GameUnitOfWork
from app.domain.world import WorldSnapshot
from app.services.market_components import MarketComponents
from app.services.market_demand import MarketDemandResolver
from app.services.player_market_preparation import PlayerMarketPreparation
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


@dataclass(frozen=True, slots=True)
class StockReadInputs:
    """Hold the authoritative facts read in one short transaction."""

    owned: tuple[OwnedVehicle, ...]
    offers: tuple[ContractOffer, ...]
    arrivals: tuple[MarketArrival, ...]
    status: PreparationStatus
    used: frozenset[str]
    bindings: dict[str, str]


@dataclass(frozen=True, slots=True)
class StockDemandProjection:
    """Hold demand and catalogue scope derived from one player snapshot."""

    reference: WorldSnapshot
    demands: tuple[MarketDemand, ...]
    cities: tuple[str, ...]
    template_scopes: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class StockPublicationPlan:
    """Hold writes calculated before opening the publication transaction."""

    offers: tuple[ContractOffer, ...]
    bindings: tuple[tuple[str, RouteReference], ...]
    coverage: tuple[VehicleCoverageDiagnostic, ...]


@dataclass(slots=True)
class StockPublicationService:
    """Own fenced publication, leaving selection and routing elsewhere."""

    unit: GameUnitOfWork
    market: MarketComponents
    preparation: PlayerMarketPreparation
    demand: MarketDemandResolver
    guard: Callable[[], bool]

    def read(self) -> StockSnapshot:
        """Read one revision, then build candidates outside the writer."""
        started = perf_counter()
        prep = self.preparation
        stock = prep.stock
        templates = prep.templates
        assert stock is not None and templates is not None
        now = prep.clock()
        inputs = self._read_inputs()
        snapshot_ms = (perf_counter() - started) * 1000
        projection = self._resolve_demand(inputs, now)
        phase = perf_counter()
        prepared_templates = templates.scoped_templates(
            projection.template_scopes
        )
        templates_ms = (perf_counter() - phase) * 1000
        phase = perf_counter()
        candidates = self.market.candidates.build(
            projection.cities,
            tuple(d.vehicle for d in projection.demands),
        )
        candidates_ms = (perf_counter() - phase) * 1000
        phase = perf_counter()
        ready, evidence = self._read_readiness(candidates)
        readiness_ms = (perf_counter() - phase) * 1000
        snapshot = self._assemble_snapshot(
            inputs,
            projection,
            candidates,
            ready,
            prepared_templates,
            evidence,
            now,
        )
        LOGGER.info(
            "Market preparation snapshot read",
            extra={
                "event": "market.stock_snapshot",
                "data": {
                    "demand_count": len(projection.demands),
                    "candidate_count": len(candidates),
                    "ready_count": len(ready),
                    "snapshot_ms": round(snapshot_ms, 3),
                    "templates_ms": round(templates_ms, 3),
                    "candidates_ms": round(candidates_ms, 3),
                    "readiness_ms": round(readiness_ms, 3),
                },
            },
        )
        return snapshot

    def _read_inputs(self) -> StockReadInputs:
        """Read player, job and stock facts in one short transaction."""
        prep = self.preparation
        stock = prep.stock
        templates = prep.templates
        assert stock is not None and templates is not None
        with self.unit.read_transaction():
            owned = self.unit.repository.list_vehicles()
            offers = self.unit.repository.list_offers()
            arrivals = stock.arrivals()
            status = prep.jobs.status(prep.user_id)
            used, bindings = stock.used(), stock.bindings()
        assert status is not None
        return StockReadInputs(owned, offers, arrivals, status, used, bindings)

    def _resolve_demand(
        self, inputs: StockReadInputs, now: float
    ) -> StockDemandProjection:
        """Resolve active player demand and its bounded catalogue scopes."""
        reference = self.market.candidates.reference()
        demands = self.demand.resolve(inputs.owned, inputs.arrivals, now)
        cities = tuple(sorted({d.vehicle.city_uid for d in demands}))
        scopes = tuple(
            sorted({(d.vehicle.city_uid, d.vehicle.model_id) for d in demands})
        )
        return StockDemandProjection(reference, demands, cities, scopes)

    def _read_readiness(
        self, candidates: tuple[MarketCandidate, ...]
    ) -> tuple[tuple[MarketCandidate, ...], tuple[RelationDemandState, ...]]:
        """Read reusable route evidence for one candidate collection."""
        prep = self.preparation
        pairs = required_relations(candidates)
        with prep.readiness.reading(pairs):
            ready = prep.ready_candidates(candidates)
            evidence = tuple(
                prep.demand_state(*pair) for pair in required_relations(ready)
            )
        return ready, evidence

    def _assemble_snapshot(
        self,
        inputs: StockReadInputs,
        projection: StockDemandProjection,
        candidates: tuple[MarketCandidate, ...],
        ready: tuple[MarketCandidate, ...],
        templates: tuple[PreparedTemplate, ...],
        evidence: tuple[RelationDemandState, ...],
        now: float,
    ) -> StockSnapshot:
        """Assemble immutable planning inputs without further reads."""
        return StockSnapshot(
            inputs.owned,
            inputs.offers,
            inputs.arrivals,
            inputs.status,
            projection.reference,
            projection.demands,
            candidates,
            ready,
            templates,
            inputs.used,
            inputs.bindings,
            evidence,
            now,
            frozenset(
                (trade_key(c), v.vehicle.vehicle_id)
                for c in ready
                for v in c.vehicles
            ),
            tuple(
                offer
                for offer in inputs.offers
                if offer.is_available(now, self.market.model_id)
                and self.market.candidates.structurally_current(offer)
            ),
            tuple(
                template
                for template in templates
                if template.offer.is_available(now, self.market.model_id)
                and self.market.candidates.structurally_current(template.offer)
            ),
            projection.template_scopes,
        )

    def unchanged(self, snapshot: StockSnapshot) -> bool:
        """Recheck inputs in the active publication transaction."""
        prep = self.preparation
        stock = prep.stock
        templates = prep.templates
        assert stock is not None and templates is not None
        return (
            self.guard()
            and self.unit.repository.list_vehicles() == snapshot.owned
            and self.unit.repository.list_offers() == snapshot.offers
            and stock.arrivals() == snapshot.arrivals
            and prep.jobs.status(prep.user_id) == snapshot.status
            and stock.used() == snapshot.used
            and stock.bindings() == snapshot.bindings
            and templates.scoped_templates(snapshot.template_scopes)
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
    ) -> bool:
        """Commit new stock, private snapshots and diagnostics together."""
        started = perf_counter()
        plan = self._build_publication_plan(snapshot, issued)
        if not self._commit_publication(snapshot, templates, issued, plan):
            return False
        if templates or issued:
            LOGGER.info(
                "Prepared stock published",
                extra={
                    "event": "market.stock_published",
                    "data": {
                        "template_count": len(templates),
                        "personal_offer_count": len(issued),
                        "generation": snapshot.status.generation,
                        "publication_ms": round(
                            (perf_counter() - started) * 1000, 3
                        ),
                    },
                },
            )
        return True

    def _build_publication_plan(
        self,
        snapshot: StockSnapshot,
        issued: tuple[tuple[str, ContractOffer], ...],
    ) -> StockPublicationPlan:
        """Calculate personal offers, coverage and reusable route bindings."""
        prep = self.preparation
        offers = snapshot.offers + tuple(offer for _, offer in issued)
        coverage = tuple(
            self.market.vehicle_coverage.diagnose(
                d.vehicle,
                snapshot.candidates,
                snapshot.ready,
                snapshot.usable_offers + tuple(o for _, o in issued),
            )
            for d in snapshot.demands
            if d.transport_id is None
        )
        pairs = tuple(
            (
                offer.origin.facility_uid,
                offer.destination.facility_uid,
            )
            for offer in offers
        )
        with prep.readiness.reading(pairs):
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
        return StockPublicationPlan(offers, bindings, coverage)

    def _commit_publication(
        self,
        snapshot: StockSnapshot,
        templates: tuple[PreparedTemplate, ...],
        issued: tuple[tuple[str, ContractOffer], ...],
        plan: StockPublicationPlan,
    ) -> bool:
        """Fence and commit one previously calculated publication plan."""
        prep = self.preparation
        stock = prep.stock
        template_store = prep.templates
        assert stock is not None and template_store is not None
        by_id = {offer.id: offer for offer in plan.offers}
        pairs = tuple(
            (
                by_id[offer_id].origin.facility_uid,
                by_id[offer_id].destination.facility_uid,
            )
            for offer_id, _ in plan.bindings
        )
        with self.unit.transaction(), prep.readiness.reading(pairs):
            if not self.unchanged(snapshot):
                return False
            # References outside current demand must also remain current.
            if any(
                prep.readiness.ready(
                    by_id[offer_id].origin.facility_uid,
                    by_id[offer_id].destination.facility_uid,
                )
                != ref
                for offer_id, ref in plan.bindings
            ):
                return False
            for template in templates:
                template_store.add(template)
            for template_id, offer in issued:
                stock.issue(template_id, offer)
            prep.references.replace(plan.bindings)
            prep.jobs.publish_diagnostics(
                prep.user_id,
                snapshot.status.generation,
                plan.coverage,
            )
        return True
