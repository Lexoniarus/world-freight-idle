"""Resolve current, arriving and catalogue demand without vehicle mutation."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.economics import VehicleCostProfile
from app.domain.game import OwnedVehicle
from app.domain.market import MarketVehicle
from app.domain.market_compatibility import planning_vehicle
from app.domain.market_profiles import vehicle_scale_for_segment
from app.domain.market_stock import MarketArrival, MarketDemand
from app.services.market_candidates import MarketCandidateService


@dataclass(slots=True)
class MarketDemandResolver:
    """Own the distinction between preparation and dispatch availability."""

    candidates: MarketCandidateService

    def resolve(
        self,
        owned: Sequence[OwnedVehicle],
        arrivals: tuple[MarketArrival, ...],
        now: float,
    ) -> tuple[MarketDemand, ...]:
        """Project concrete idle and pending-arrival vehicle demand."""
        models = {
            model.id: model
            for model in self.candidates.catalogue.list_models()
        }
        result = [
            MarketDemand(vehicle, now)
            for vehicle in self.candidates.resolve_fleet(owned)
        ]
        by_id = {vehicle.id: vehicle for vehicle in owned}
        for arrival in arrivals:
            vehicle = by_id[arrival.vehicle_id]
            if vehicle.status != "enroute":
                raise ValueError("Arrival requires an enroute owned vehicle.")
            result.append(
                MarketDemand(
                    planning_vehicle(
                        vehicle,
                        models[vehicle.model_id or ""],
                        arrival.destination,
                    ),
                    arrival.arrives_at,
                    arrival.transport_id,
                )
            )
        return tuple(
            sorted(
                result,
                key=lambda d: (
                    d.catalogue_only,
                    d.vehicle.capacity_tons,
                    d.vehicle.vehicle_id,
                ),
            )
        )

    def catalogue(self, now: float) -> tuple[MarketDemand, ...]:
        """Enumerate lightweight global city/model preparation contexts."""
        facilities: dict[str, str] = {}
        for facility in sorted(
            self.candidates.reference().facilities,
            key=lambda item: item.facility_uid,
        ):
            if facility.is_routable():
                facilities.setdefault(
                    facility.address.city.city_uid,
                    facility.facility_uid,
                )
        demands = []
        for city_uid, facility_uid in sorted(facilities.items()):
            for model in sorted(
                self.candidates.catalogue.list_models(),
                key=lambda item: item.id,
            ):
                if model.mode != "truck":
                    continue
                demands.append(
                    MarketDemand(
                        MarketVehicle(
                            f"catalogue:{city_uid}:{model.id}",
                            model.id,
                            city_uid,
                            model.mode,
                            model.capacity_tons,
                            vehicle_scale_for_segment(model.segment),
                            model.transport_capabilities,
                            VehicleCostProfile(
                                model.maintenance_eur_per_1000_km / 1000
                            ),
                            model.energy,
                            facility_uid,
                        ),
                        now,
                        catalogue_only=True,
                    )
                )
        return tuple(demands)
