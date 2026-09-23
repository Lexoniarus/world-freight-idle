"""Domain data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VehicleStatus = Literal["idle", "enroute"]


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
