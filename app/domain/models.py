"""Domain data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

TransportMode = Literal["truck"]
VehicleStatus = Literal["idle", "enroute"]


@dataclass(frozen=True, slots=True)
class Hub:
    """A real, geocodable freight endpoint."""

    id: str
    city: str
    label: str
    address: str
    country: str


@dataclass(frozen=True, slots=True)
class CargoType:
    """A fictional cargo category used by the contract generator."""

    name: str
    min_tons: float
    max_tons: float
    rate_eur_per_km_ton: float


@dataclass(frozen=True, slots=True)
class Contract:
    """A fictional transport job between real addresses."""

    id: str
    origin_hub_id: str
    destination_hub_id: str
    shipper_name: str
    consignee_name: str
    cargo: str
    tons: float
    created_at: float
    expires_at: float
    mode: TransportMode = "truck"


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Real route geometry and travel estimate from a routing provider."""

    distance_km: float
    duration_seconds: float
    route_geojson: dict[str, Any]
    provider: str


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """Commercial calculation for one routed contract."""

    payout_eur: int
    operating_cost_eur: int
    profit_eur: int


@dataclass(frozen=True, slots=True)
class VehicleImage:
    """Verified catalogue photograph with its mandatory provenance."""

    url: str
    source_url: str
    author: str
    license_name: str
    license_url: str
    attribution: str
    scope: str


@dataclass(frozen=True, slots=True)
class VehicleModel:
    """Server-owned purchase offer, separate from technical source records."""

    id: str
    name: str
    manufacturer: str
    powertrain: str
    capacity_tons: float
    price_eur: int
    operating_cost_eur_per_km: float
    unlock_reputation: int
    mode: str = "truck"
    image: VehicleImage | None = None
