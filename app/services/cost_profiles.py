"""Resolve explicit vehicle catalogue maintenance without heuristics."""

from dataclasses import dataclass

from app.domain.economics import VehicleCostProfile
from app.domain.errors import UnresolvedVehicleModel
from app.domain.ports import VehicleCatalogue


@dataclass(slots=True)
class VehicleCostResolver:
    """Resolve a new quote's costs through an injected reference port."""

    catalogue: VehicleCatalogue

    def resolve(self, model_id: str | None) -> VehicleCostProfile:
        """Reject unresolved models instead of reusing aggregate old costs."""
        for model in self.catalogue.list_models():
            if model.id == model_id:
                return VehicleCostProfile(
                    model.maintenance_eur_per_1000_km / 1000
                )
        raise UnresolvedVehicleModel("Fahrzeugkostenprofil nicht auflösbar.")
