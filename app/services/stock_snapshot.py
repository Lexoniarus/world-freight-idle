"""Read immutable market planning snapshots without publishing stock."""

import logging
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


@dataclass(slots=True)
class StockSnapshotReader:
    """Read and project one authoritative player-market revision."""

    unit: GameUnitOfWork
    market: MarketComponents
    preparation: PlayerMarketPreparation
    demand: MarketDemandResolver

    def read(self) -> StockSnapshot:
        """Read one revision and build its immutable planning snapshot."""
        started = perf_counter()
        preparation = self.preparation
        templates = preparation.templates
        assert preparation.stock is not None and templates is not None
        now = preparation.clock()
        inputs = self.read_inputs()
        snapshot_ms = (perf_counter() - started) * 1000
        projection = self.resolve_demand(inputs, now)
        phase = perf_counter()
        prepared_templates = templates.scoped_templates(
            projection.template_scopes
        )
        templates_ms = (perf_counter() - phase) * 1000
        phase = perf_counter()
        candidates = self.market.candidates.build(
            projection.cities,
            tuple(item.vehicle for item in projection.demands),
        )
        candidates_ms = (perf_counter() - phase) * 1000
        phase = perf_counter()
        ready, evidence = self.read_readiness(candidates)
        readiness_ms = (perf_counter() - phase) * 1000
        snapshot = self.assemble(
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

    def read_inputs(self) -> StockReadInputs:
        """Read player, job and stock facts in one short transaction."""
        preparation = self.preparation
        stock = preparation.stock
        assert stock is not None
        with self.unit.read_transaction():
            owned = self.unit.repository.list_vehicles()
            offers = self.unit.repository.list_offers()
            arrivals = stock.arrivals()
            status = preparation.jobs.status(preparation.user_id)
            used, bindings = stock.used(), stock.bindings()
        assert status is not None
        return StockReadInputs(owned, offers, arrivals, status, used, bindings)

    def resolve_demand(
        self, inputs: StockReadInputs, now: float
    ) -> StockDemandProjection:
        """Resolve active player demand and its bounded catalogue scopes."""
        reference = self.market.candidates.reference()
        demands = self.demand.resolve(inputs.owned, inputs.arrivals, now)
        cities = tuple(sorted({item.vehicle.city_uid for item in demands}))
        scopes = tuple(
            sorted(
                {
                    (item.vehicle.city_uid, item.vehicle.model_id)
                    for item in demands
                }
            )
        )
        return StockDemandProjection(reference, demands, cities, scopes)

    def read_readiness(
        self, candidates: tuple[MarketCandidate, ...]
    ) -> tuple[tuple[MarketCandidate, ...], tuple[RelationDemandState, ...]]:
        """Read reusable route evidence for one candidate collection."""
        preparation = self.preparation
        pairs = required_relations(candidates)
        with preparation.readiness.reading(pairs):
            ready = preparation.ready_candidates(candidates)
            evidence = tuple(
                preparation.demand_state(*pair)
                for pair in required_relations(ready)
            )
        return ready, evidence

    def assemble(
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
                (trade_key(candidate), vehicle.vehicle.vehicle_id)
                for candidate in ready
                for vehicle in candidate.vehicles
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
