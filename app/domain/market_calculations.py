"""Pure Market v2 distance, weighting and shipment calculations."""

import math

from app.domain.geography import Coordinates
from app.domain.market import TradeOption
from app.domain.market_profiles import DistanceBand
from app.domain.validation import require_finite

SHORT_DISTANCE_KM = 150.0
MEDIUM_DISTANCE_KM = 600.0
EARTH_MEAN_RADIUS_KM = 6371.0088
ORIGIN_DOCUMENTED_WEIGHT = 1.45
DESTINATION_DOCUMENTED_WEIGHT = 1.25
EXACT_MATCH_WEIGHT = 1.25
CONFIDENCE_BASE_WEIGHT = 0.5
PRIORITY_BASE_WEIGHT = 0.5


def great_circle_km(origin: Coordinates, destination: Coordinates) -> float:
    """Estimate distance deterministically from WGS84 facility points."""
    lat1, lat2 = (
        math.radians(origin.latitude),
        math.radians(destination.latitude),
    )
    dlat = lat2 - lat1
    dlon = math.radians(destination.longitude - origin.longitude)
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return (
        2 * EARTH_MEAN_RADIUS_KM * math.asin(math.sqrt(min(1, max(0, value))))
    )


def distance_band(distance_km: float) -> DistanceBand:
    """Use the V18 audit boundaries, including their upper endpoints."""
    require_finite(distance_km, "Estimated distance")
    if distance_km <= SHORT_DISTANCE_KM:
        return "short"
    if distance_km <= MEDIUM_DISTANCE_KM:
        return "medium"
    return "long"


def evidence_weight(trade: TradeOption) -> float:
    """Preserve sourced, confident, prioritized and exact NHM weighting."""
    origin = trade.origin_cargo
    destination = trade.destination_cargo
    return (
        (ORIGIN_DOCUMENTED_WEIGHT if origin.evidence_type != "derived" else 1)
        * (
            DESTINATION_DOCUMENTED_WEIGHT
            if destination.evidence_type != "derived"
            else 1
        )
        * (EXACT_MATCH_WEIGHT if trade.match_type == "exact" else 1)
        * (CONFIDENCE_BASE_WEIGHT + origin.confidence + destination.confidence)
        * (
            PRIORITY_BASE_WEIGHT
            + origin.priority_score
            + destination.priority_score
        )
    )


def shipment_tons(capacity_tons: float, load_factor: float) -> float:
    """Floor to hundredths without exceeding purchased vehicle capacity."""
    require_finite(capacity_tons, "Vehicle capacity", 0.01)
    require_finite(load_factor, "Load factor")
    if not 0 < load_factor <= 1:
        raise ValueError("Invalid load factor.")
    return max(0.01, math.floor(capacity_tons * load_factor * 100) / 100)
