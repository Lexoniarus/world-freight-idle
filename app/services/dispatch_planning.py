"""Plan road sections and quote the selected vehicle without persistence."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.dispatch_journey import plan_dispatch_journey
from app.domain.economics import journey_costs
from app.domain.game import OwnedVehicle
from app.domain.ports import TruckRouter, WorldCatalogue
from app.domain.pricing import calculate_price
from app.domain.results import ContractQuote
from app.domain.routes import DispatchRoutePlan, RouteSnapshot
from app.domain.routing_anchor_ports import RoutingAnchorResolverPort
from app.domain.world import FacilityLocationSnapshot
from app.domain.world_scopes import WorldScope
from app.services.cost_profiles import VehicleCostResolver


@dataclass(slots=True)
class DispatchPlanningService:
    """Orchestrate injected routing and deterministic dispatch planning."""

    router: TruckRouter
    costs: VehicleCostResolver
    anchors: RoutingAnchorResolverPort
    world: WorldCatalogue

    async def route(
        self, start: FacilityLocationSnapshot, contract: ContractOffer
    ) -> DispatchRoutePlan:
        """Route pickup approach and freight before any write transaction."""
        approach = None
        if start.facility_uid != contract.origin.facility_uid:
            approach = await self._route_between(start, contract.origin)
        delivery = await self._route_between(
            contract.origin, contract.destination
        )
        return DispatchRoutePlan(
            start, contract.origin, contract.destination, delivery, approach
        )

    async def _route_between(
        self,
        start: FacilityLocationSnapshot,
        destination: FacilityLocationSnapshot,
    ) -> RouteSnapshot:
        """Route facility identities through validated truck anchors."""
        world = WorldScope(self.world.read())
        origin = await self.anchors.resolve(world.facility(start.facility_uid))
        target = await self.anchors.resolve(
            world.facility(destination.facility_uid)
        )
        if (
            origin.validation_status != "validated"
            or origin.anchor is None
            or target.validation_status != "validated"
            or target.anchor is None
        ):
            raise ValueError(
                "Facility besitzt keinen validierten Truck-Routing-Anchor."
            )
        return await self.router.route(
            origin.anchor.latitude,
            origin.anchor.longitude,
            target.anchor.latitude,
            target.anchor.longitude,
        )

    def quote(
        self,
        contract: ContractOffer,
        route: DispatchRoutePlan,
        vehicle: OwnedVehicle,
        time_scale: float,
    ) -> ContractQuote:
        """Compose journey and economics from revalidated purchased values."""
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
