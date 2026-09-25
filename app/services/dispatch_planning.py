"""Plan road sections and quote the selected vehicle without persistence."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.dispatch_journey import plan_dispatch_journey
from app.domain.economics import journey_costs
from app.domain.game import OwnedVehicle
from app.domain.ports import TruckRouter
from app.domain.pricing import calculate_price
from app.domain.results import ContractQuote
from app.domain.routes import DispatchRoutePlan, RouteSnapshot
from app.domain.world import FacilityLocationSnapshot
from app.services.cost_profiles import VehicleCostResolver


@dataclass(slots=True)
class DispatchPlanningService:
    """Orchestrate an injected router and deterministic dispatch planning."""

    router: TruckRouter
    costs: VehicleCostResolver

    async def route(
        self, start: FacilityLocationSnapshot, contract: ContractOffer
    ) -> DispatchRoutePlan:
        """Route pickup approach and freight before any write transaction."""
        approach = None
        if (
            start.facility_uid != contract.origin.facility_uid
            and start.coordinates != contract.origin.coordinates
        ):
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
        """Require coordinates before asking the road provider for a leg."""
        origin, target = start.coordinates, destination.coordinates
        if origin is None or target is None:
            raise ValueError("Fahrtplan enthält keine routbaren Koordinaten.")
        return await self.router.route(
            origin.latitude,
            origin.longitude,
            target.latitude,
            target.longitude,
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
