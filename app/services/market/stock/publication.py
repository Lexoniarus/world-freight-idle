"""Publish stock against an authoritative immutable planning snapshot."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from app.domain.contracts import ContractOffer
from app.domain.market import VehicleCoverageDiagnostic
from app.domain.market_stock import PreparedTemplate
from app.domain.routing_readiness import RouteReference
from app.domain.state_ports import GameUnitOfWork
from app.services.market.components import MarketComponents
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_stock import PlayerMarketStockContext
from app.services.market.stock.snapshot import StockSnapshot

LOGGER = logging.getLogger(__name__)


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
    player_demand: PlayerMarketDemandService
    routes: PlayerMarketRouteService
    stock_context: PlayerMarketStockContext
    guard: Callable[[], bool]

    def unchanged(self, snapshot: StockSnapshot) -> bool:
        """Recheck inputs in the active publication transaction."""
        stock = self.stock_context.stock
        templates = self.stock_context.templates
        return (
            self.guard()
            and self.unit.repository.list_vehicles() == snapshot.owned
            and self.unit.repository.list_offers() == snapshot.offers
            and stock.arrivals() == snapshot.arrivals
            and self.player_demand.status() == snapshot.status
            and stock.used() == snapshot.used
            and stock.bindings() == snapshot.bindings
            and templates.scoped_templates(snapshot.template_scopes)
            == snapshot.templates
            and self.market.candidates.reference() == snapshot.reference
            and tuple(
                self.routes.demand_state(s.origin_uid, s.destination_uid)
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
        with self.routes.readiness.reading(pairs):
            bindings = tuple(
                (offer.id, reference)
                for offer in offers
                if self.market.candidates.structurally_current(offer)
                and (
                    reference := self.routes.readiness.ready(
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
        stock = self.stock_context.stock
        template_store = self.stock_context.templates
        by_id = {offer.id: offer for offer in plan.offers}
        pairs = tuple(
            (
                by_id[offer_id].origin.facility_uid,
                by_id[offer_id].destination.facility_uid,
            )
            for offer_id, _ in plan.bindings
        )
        with self.unit.transaction(), self.routes.readiness.reading(pairs):
            if not self.unchanged(snapshot):
                return False
            # References outside current demand must also remain current.
            if any(
                self.routes.readiness.ready(
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
            self.routes.references.replace(plan.bindings)
            self.player_demand.publish_diagnostics(
                snapshot.status.generation,
                plan.coverage,
            )
        return True
