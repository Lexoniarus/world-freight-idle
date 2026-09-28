"""Plan road sections and quote the selected vehicle without persistence."""

import time
from dataclasses import dataclass, field

from app.domain.contracts import ContractOffer
from app.domain.dispatch_journey import plan_dispatch_journey
from app.domain.economics import journey_costs
from app.domain.game import OwnedVehicle
from app.domain.ports import TruckRouter, WorldCatalogue
from app.domain.pricing import calculate_price
from app.domain.results import ContractQuote
from app.domain.routes import DispatchRoutePlan, RouteSnapshot
from app.domain.routing_anchor_ports import RoutingAnchorResolverPort
from app.domain.routing_anchors import RoutingCandidate
from app.domain.world import FacilityLocationSnapshot
from app.domain.world_scopes import WorldScope
from app.services.cost_profiles import VehicleCostResolver
from app.services.market_preparation import MarketPreparationService
from app.services.routing_connections import RoutingConnectionValidator


@dataclass(slots=True)
class DispatchPlanningService:
    """Orchestrate injected routing and deterministic dispatch planning."""

    router: TruckRouter
    costs: VehicleCostResolver
    anchors: RoutingAnchorResolverPort
    world: WorldCatalogue
    preparation: MarketPreparationService | None = None
    connections: RoutingConnectionValidator = field(
        default_factory=RoutingConnectionValidator
    )

    async def route(
        self, start: FacilityLocationSnapshot, contract: ContractOffer
    ) -> DispatchRoutePlan:
        """Load prepared approach and delivery before a write transaction."""
        if self.preparation is not None and not self.preparation.retained(
            contract
        ):
            raise ValueError("Straßenverbindung wird vorbereitet.")
        approach = None
        selected: dict[str, RoutingCandidate] = {}
        if start.facility_uid != contract.origin.facility_uid:
            approach = await self._route_between(
                start, contract.origin, selected
            )
        delivery = await self._route_between(
            contract.origin, contract.destination, selected
        )
        return DispatchRoutePlan(
            start, contract.origin, contract.destination, delivery, approach
        )

    async def _route_between(
        self,
        start: FacilityLocationSnapshot,
        destination: FacilityLocationSnapshot,
        selected: dict[str, RoutingCandidate] | None = None,
    ) -> RouteSnapshot:
        """Resolve a prepared relation at the dispatch boundary."""
        if self.preparation is not None:
            return self.preparation.readiness.load(
                start.facility_uid, destination.facility_uid
            ).to_snapshot()
        world = WorldScope(self.world.read())
        connection = await self.connections.validate(
            world.facility(start.facility_uid),
            world.facility(destination.facility_uid),
            self.router,
            self.anchors,
            time.time,
            fixed=selected,
        )
        if selected is not None:
            for anchor in (connection.origin, connection.destination):
                assert anchor.anchor is not None
                selected[anchor.facility_uid] = RoutingCandidate(
                    anchor.anchor,
                    anchor.snap_distance_m or 0.0,
                    anchor.provider,
                    anchor.provider_revision,
                    anchor.method,
                )
        return connection.forward

    def quote(
        self,
        contract: ContractOffer,
        route: DispatchRoutePlan,
        vehicle: OwnedVehicle,
        time_scale: float,
    ) -> ContractQuote:
        """Compose journey and economics from revalidated purchased values."""
        if self.preparation is not None:
            if not self.preparation.retained(contract):
                raise ValueError("Straßenverbindung wurde geändert.")
            current = self.preparation.readiness
            if (
                current.load(
                    contract.origin.facility_uid,
                    contract.destination.facility_uid,
                ).to_snapshot()
                != route.delivery
            ):
                raise ValueError("Lieferroute wurde geändert.")
            if (
                route.approach is not None
                and current.load(
                    route.start.facility_uid, contract.origin.facility_uid
                ).to_snapshot()
                != route.approach
            ):
                raise ValueError("Anfahrtsroute wurde geändert.")
        if vehicle.location != route.start:
            raise ValueError(
                "Fahrzeugstandort wurde während der Planung geändert."
            )
        profile = self.costs.resolve(vehicle.model_id)
        cost = profile.maintenance_eur_per_km
        context = contract.market_context
        if context is None or context.tariff is None:
            raise ValueError("Gespeicherter NHM-Tarif fehlt; Markt erneuern.")
        journey = plan_dispatch_journey(
            route,
            vehicle.top_speed_kmh,
            vehicle.energy,
            vehicle.energy_level,
            time_scale,
        )
        price = calculate_price(
            contract.tons,
            route.delivery.distance_km,
            journey_costs(journey, profile),
            contract.rate_eur_per_km_ton,
            minimum_eur_per_km=context.tariff.minimum_eur_per_km,
        )
        return ContractQuote(
            contract,
            route.total_route,
            price,
            vehicle.id,
            cost,
            journey,
            route,
        )
