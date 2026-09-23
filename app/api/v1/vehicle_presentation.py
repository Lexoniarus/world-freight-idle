"""Enrich fleet presentation without rewriting owned vehicle snapshots."""

from app.domain.errors import CatalogueError
from app.domain.ports import VehicleCatalogue


def present_vehicles(
    vehicles: list[dict], catalogue: VehicleCatalogue
) -> list[dict]:
    """Attach photographs without changing owned gameplay values."""
    try:
        images = {model.id: model.image for model in catalogue.list_models()}
    except CatalogueError:
        images = {}
    return [
        {**vehicle, "image": image.to_dict() if image else None}
        for vehicle in vehicles
        for image in [images.get(vehicle.get("model_id") or "")]
    ]
