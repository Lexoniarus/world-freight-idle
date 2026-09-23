"""Stable HTTP projections of typed game use-case results."""

from typing import Any

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle
from app.domain.results import ContractQuote, FleetCatalogue, GameSnapshot
from app.domain.transports import ActiveTransport


def project_contract(offer: ContractOffer) -> dict[str, Any]:
    """Expose an offer using the established v1 field names."""
    return offer.to_dict()


def project_vehicle(vehicle: OwnedVehicle) -> dict[str, Any]:
    """Expose owned model values and the saved public facility location."""
    return {
        **vehicle.to_dict(),
        "hub": vehicle.location.to_dict() if vehicle.location else None,
    }


def project_quote(quote: ContractQuote) -> dict[str, Any]:
    """Expose the selected vehicle, historical endpoints and real route."""
    return {
        "distance_km": quote.route.distance_km,
        "duration_seconds": quote.route.duration_seconds,
        "route_geojson": {
            "type": "LineString",
            "coordinates": [list(point) for point in quote.route.coordinates],
        },
        "provider": quote.route.provider,
        **quote.economics.to_dict(),
        "vehicle_id": quote.vehicle_id,
        "operating_cost_eur_per_km": quote.operating_cost_eur_per_km,
        "origin": quote.contract.origin.to_dict(),
        "destination": quote.contract.destination.to_dict(),
        "contract": project_contract(quote.contract),
    }


def project_transport(trip: ActiveTransport) -> dict[str, Any]:
    """Expose tracking without leaking persistence lifecycle columns."""
    return {
        "id": trip.id,
        "vehicle_id": trip.vehicle_id,
        "contract": project_contract(trip.contract),
        "origin": trip.origin.to_dict(),
        "destination": trip.destination.to_dict(),
        "origin_snapshot": trip.origin.to_dict(),
        "destination_snapshot": trip.destination.to_dict(),
        "route_geojson": {
            "type": "LineString",
            "coordinates": [list(point) for point in trip.route.coordinates],
        },
        "distance_km": trip.route.distance_km,
        "routing_duration_seconds": trip.route.duration_seconds,
        "provider": trip.route.provider,
        "departed_at": trip.departed_at,
        "arrives_at": trip.arrives_at,
        "payout_eur": trip.payout_eur,
        "operating_cost_eur": trip.operating_cost_eur,
        "profit_eur": trip.payout_eur - trip.operating_cost_eur,
    }


def project_state(state: GameSnapshot) -> dict[str, Any]:
    """Expose the complete state for an explicitly requested full read."""
    vehicles = [project_vehicle(item) for item in state.vehicles]
    return {
        "server_time": state.server_time,
        "time_scale": state.time_scale,
        "player": state.player.to_dict(),
        "vehicles": vehicles,
        "active_trips": [project_transport(item) for item in state.transports],
        "contracts": [project_contract(item) for item in state.contracts],
        "hubs": [item["hub"] for item in vehicles],
    }


def project_dashboard(state: GameSnapshot) -> dict[str, Any]:
    """Expose startup counters without generating a global market."""
    return {
        "server_time": state.server_time,
        "time_scale": state.time_scale,
        "player": state.player.to_dict(),
        "available_contracts": 0,
        "idle_vehicles": sum(item.status == "idle" for item in state.vehicles),
        "active_transports": len(state.transports),
        "featured_contracts": [],
        "vehicles": [project_vehicle(item) for item in state.vehicles],
        "transports": [project_transport(item) for item in state.transports],
    }


def project_catalogue(catalogue: FleetCatalogue) -> dict[str, Any]:
    """Expose read-only model offers and the compatible delivery label."""
    return {
        "models": [model.to_dict() for model in catalogue.models],
        "delivery_hub": catalogue.delivery_location.label,
    }
