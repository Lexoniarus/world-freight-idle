"""Resolve current and arriving vehicle demand without vehicle mutation."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.game import OwnedVehicle
from app.domain.market_compatibility import planning_vehicle
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
        """Project concrete idle and destination demand only."""
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
                    d.vehicle.capacity_tons,
                    d.vehicle.vehicle_id,
                ),
            )
        )
