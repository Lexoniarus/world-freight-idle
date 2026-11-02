"""Plan road sections and quote the selected vehicle without persistence."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.dispatch_journey import plan_dispatch_journey
from app.domain.economics import journey_costs
from app.domain.game import OwnedVehicle
from app.domain.pricing import calculate_price
from app.domain.results import ContractQuote
from app.domain.routes import DispatchRoutePlan, RouteSnapshot
from app.domain.world import FacilityLocationSnapshot
from app.services.cost_profiles import VehicleCostResolver
from app.services.market.player_routes import PlayerMarketRouteService


@dataclass(slots=True)
class DispatchPlanningService:
    """Orchestrate injected routing and deterministic dispatch planning."""

    costs: VehicleCostResolver
    routes: PlayerMarketRouteService

    async def route(
        self, start: FacilityLocationSnapshot, contract: ContractOffer
    ) -> DispatchRoutePlan:
        """Load prepared approach and delivery before a write transaction."""
        if not self.routes.retained_current(contract):
            raise ValueError("Straßenverbindung wird vorbereitet.")
        approach = None
        if start.facility_uid != contract.origin.facility_uid:
            approach = self._load_prepared_route(start, contract.origin)
        delivery = self._load_prepared_route(
            contract.origin,
            contract.destination,
        )
        return DispatchRoutePlan(
            start, contract.origin, contract.destination, delivery, approach
        )

    def _load_prepared_route(
        self,
        start: FacilityLocationSnapshot,
        destination: FacilityLocationSnapshot,
    ) -> RouteSnapshot:
        """Load one certified relation without dispatch-time providers."""
        return self.routes.readiness.load(
            start.facility_uid,
            destination.facility_uid,
        ).to_snapshot()

    def quote(
        self,
        contract: ContractOffer,
        route: DispatchRoutePlan,
        vehicle: OwnedVehicle,
        time_scale: float,
    ) -> ContractQuote:
        """Compose journey and economics from revalidated purchased values."""
        if not self.routes.retained_current(contract):
            raise ValueError("Straßenverbindung wurde geändert.")
        current = self.routes.readiness
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
