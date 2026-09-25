"""Stable HTTP projections of typed game use-case results."""

from dataclasses import asdict
from typing import Any

from app.api.v1.dispatch_projection import project_dispatch_route
from app.api.v1.location_projection import project_location
from app.domain.cargo import DocumentedCargo, FacilityNhmProfile
from app.domain.contracts import (
    ContractOffer,
    ContractOfferSnapshot,
    HistoricalContractSnapshot,
)
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.results import (
    AvailableContract,
    ContractQuote,
    FleetCatalogue,
    GameSnapshot,
)
from app.domain.transports import ActiveTransport


def project_contract(
    offer: ContractOffer
    | ContractOfferSnapshot
    | HistoricalContractSnapshot
    | AvailableContract,
) -> dict[str, Any]:
    """Expose an offer using the established v1 field names."""
    eligible: tuple[str, ...] | None = None
    if isinstance(offer, AvailableContract):
        eligible = offer.eligible_vehicle_ids
        offer = offer.offer
    origin = project_location(offer.origin)
    destination = project_location(offer.destination)
    origin_evidence = (
        project_nhm_profile(offer.origin_cargo_evidence)
        if offer.origin_cargo_evidence
        else asdict(offer.cargo)
        if isinstance(offer.cargo, DocumentedCargo)
        else None
    )
    destination_evidence = (
        project_nhm_profile(offer.destination_cargo_evidence)
        if offer.destination_cargo_evidence
        else None
    )
    return {
        "id": offer.id,
        "market_model": offer.market_model,
        "cargo_system": offer.cargo_system,
        "origin_hub_id": offer.origin.facility_uid,
        "destination_hub_id": offer.destination.facility_uid,
        "origin_facility_uid": offer.origin.facility_uid,
        "destination_facility_uid": offer.destination.facility_uid,
        "origin": origin,
        "destination": destination,
        "shipper_name": offer.shipper_name,
        "consignee_name": offer.consignee_name,
        "cargo": offer.cargo.name,
        "cargo_code": offer.cargo.code,
        "cargo_evidence": origin_evidence,
        "origin_cargo_evidence": origin_evidence,
        "destination_cargo_evidence": destination_evidence,
        "cargo_basis": offer.cargo_basis,
        "trade_match_type": offer.trade_match_type,
        "tons": offer.tons,
        **({"payload_band": offer.payload_band} if offer.payload_band else {}),
        **(asdict(offer.market_context) if offer.market_context else {}),
        **(
            {"eligible_vehicle_ids": list(eligible)}
            if eligible is not None
            else {}
        ),
        "rate_eur_per_km_ton": offer.rate_eur_per_km_ton,
        "created_at": offer.created_at,
        "expires_at": offer.expires_at,
        "mode": offer.mode,
        "relationship_simulated": offer.relationship_simulated,
    }


def project_vehicle(
    vehicle: OwnedVehicle,
    trip: ActiveTransport | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Expose owned model values and the saved public facility location."""
    result: dict[str, Any] = {
        "energy": asdict(vehicle.energy),
        "energy_level": (
            trip.progress_at(now).energy_level
            if trip is not None
            and now is not None
            and trip.journey.energy is not None
            else vehicle.energy_level
        ),
        "top_speed_kmh": vehicle.top_speed_kmh,
        "id": vehicle.id,
        "name": vehicle.name,
        "mode": vehicle.mode,
        "model_id": vehicle.model_id,
        "capacity_tons": vehicle.capacity_tons,
        "hub_id": vehicle.facility_uid,
        "status": vehicle.status,
    }
    if vehicle.operating_cost_eur_per_km is not None:
        result["operating_cost_eur_per_km"] = vehicle.operating_cost_eur_per_km
    if vehicle.facility_uid is not None:
        result["facility_uid"] = vehicle.facility_uid
    if vehicle.location is not None:
        result["location_snapshot"] = project_location(vehicle.location)
    result["hub"] = (
        project_location(vehicle.location) if vehicle.location else None
    )
    return result


def project_quote(quote: ContractQuote) -> dict[str, Any]:
    """Expose the selected vehicle, historical endpoints and real route."""
    return {
        **project_dispatch_route(
            quote.dispatch_route, quote.contract.origin, quote.route
        ),
        "journey": asdict(quote.journey) if quote.journey else None,
        "energy_consumption": (
            quote.journey.energy.consumption_for(quote.route.distance_km)
            if quote.journey and quote.journey.energy
            else None
        ),
        "energy_stop_count": quote.journey.stop_count
        if quote.journey
        else None,
        "driving_seconds": quote.journey.driving_seconds
        if quote.journey
        else None,
        "pause_seconds": (
            quote.journey.duration_seconds - quote.journey.driving_seconds
            if quote.journey
            else None
        ),
        "total_duration_seconds": quote.journey.duration_seconds
        if quote.journey
        else None,
        "distance_km": quote.route.distance_km,
        "duration_seconds": quote.route.duration_seconds,
        "route_geojson": {
            "type": "LineString",
            "coordinates": [list(point) for point in quote.route.coordinates],
        },
        "provider": quote.route.provider,
        **asdict(quote.economics),
        "vehicle_id": quote.vehicle_id,
        "operating_cost_eur_per_km": quote.operating_cost_eur_per_km,
        "origin": project_location(quote.contract.origin),
        "destination": project_location(quote.contract.destination),
        "contract": project_contract(quote.contract),
    }


def project_transport(
    trip: ActiveTransport,
    now: float | None = None,
) -> dict[str, Any]:
    """Expose tracking without leaking persistence lifecycle columns."""
    return {
        **project_dispatch_route(trip.dispatch_route, trip.origin, trip.route),
        "journey": asdict(trip.journey),
        "progress": asdict(trip.progress_at(now)) if now is not None else None,
        "id": trip.id,
        "vehicle_id": trip.vehicle_id,
        "contract": project_contract(trip.contract),
        "origin": project_location(trip.origin),
        "destination": project_location(trip.destination),
        "origin_snapshot": project_location(trip.origin),
        "destination_snapshot": project_location(trip.destination),
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
    vehicles = project_fleet(state)
    return {
        "server_time": state.server_time,
        "time_scale": state.time_scale,
        "player": project_player(state.player),
        "vehicles": vehicles,
        "active_trips": [
            project_transport(item, state.server_time)
            for item in state.transports
        ],
        "contracts": [project_contract(item) for item in state.contracts],
        "hubs": [item["hub"] for item in vehicles],
    }


def project_dashboard(state: GameSnapshot) -> dict[str, Any]:
    """Expose startup counters without generating a global market."""
    return {
        "server_time": state.server_time,
        "time_scale": state.time_scale,
        "player": project_player(state.player),
        "available_contracts": 0,
        "idle_vehicles": sum(item.status == "idle" for item in state.vehicles),
        "active_transports": len(state.transports),
        "featured_contracts": [],
        "vehicles": project_fleet(state),
        "transports": [
            project_transport(item, state.server_time)
            for item in state.transports
        ],
    }


def project_catalogue(catalogue: FleetCatalogue) -> dict[str, Any]:
    """Expose read-only model offers and the compatible delivery label."""
    return {
        "models": [asdict(model) for model in catalogue.models],
        "delivery_hub": catalogue.delivery_location.label,
    }


def project_player(player: PlayerState) -> dict[str, int]:
    """Expose authoritative counters without mutable entity internals."""
    return {
        "cash": player.cash,
        "completed": player.completed,
        "reputation": player.reputation,
    }


def project_nhm_profile(profile: FacilityNhmProfile) -> dict[str, Any]:
    """Retain v1 evidence fields while the domain composes product values."""
    return {
        **asdict(profile.product),
        "ancestor_row_ids": list(profile.product.ancestor_row_ids),
        "role": profile.role,
        "evidence_type": profile.evidence_type,
        "confidence": profile.confidence,
        "priority_score": profile.priority_score,
        "source": asdict(profile.source) if profile.source else None,
    }


def project_fleet(state: GameSnapshot) -> list[dict[str, Any]]:
    """Project current energy without mutating persisted departure levels."""
    trips = {trip.vehicle_id: trip for trip in state.transports}
    return [
        project_vehicle(vehicle, trips.get(vehicle.id), state.server_time)
        for vehicle in state.vehicles
    ]
