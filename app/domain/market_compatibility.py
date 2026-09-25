"""Shared deterministic vehicle and shipment compatibility rules."""

from app.domain.contracts import ContractOffer
from app.domain.economics import VehicleCostProfile
from app.domain.game import OwnedVehicle
from app.domain.market import MarketVehicle
from app.domain.market_profiles import (
    NhmMarketProfile,
    vehicle_scale_for_segment,
)
from app.domain.vehicles import VehicleModel
from app.domain.world import FacilityLocationSnapshot


def market_vehicle(
    vehicle: OwnedVehicle,
    model: VehicleModel,
    location: FacilityLocationSnapshot,
) -> MarketVehicle:
    """Freeze owned capacity while resolving only reference capabilities."""
    if vehicle.model_id != model.id:
        raise ValueError("Fahrzeugmodell ist nicht auflösbar.")
    if vehicle.status != "idle":
        raise ValueError("Fahrzeug ist nicht verfügbar.")
    return MarketVehicle(
        vehicle.id,
        model.id,
        location.city.city_uid,
        vehicle.mode,
        vehicle.capacity_tons,
        vehicle_scale_for_segment(model.segment),
        model.transport_capabilities,
        VehicleCostProfile(model.maintenance_eur_per_1000_km / 1000),
        vehicle.energy,
    )


def vehicle_suitability(
    vehicle: MarketVehicle,
    profile: NhmMarketProfile,
) -> float:
    """Combine class and scale weights without choosing a vehicle."""
    capability = next(
        (
            item.suitability_game
            for item in vehicle.capabilities
            if item.transport_class == profile.transport_class
        ),
        0.0,
    )
    scale = next(
        item.suitability_game
        for item in profile.scale_profiles
        if item.vehicle_scale == vehicle.scale
    )
    return capability * scale if vehicle.mode == "truck" else 0.0


def can_carry_offer(
    vehicle: MarketVehicle,
    offer: ContractOffer,
    profile: NhmMarketProfile,
) -> bool:
    """Check current city, concrete tonnage and positive suitability."""
    return (
        vehicle.city_uid == offer.origin.city.city_uid
        and vehicle.mode == offer.mode
        and vehicle.capacity_tons >= offer.tons
        and vehicle_suitability(vehicle, profile) > 0
    )
