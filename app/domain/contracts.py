"""Immutable runtime contract snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.domain.world import CargoProfile, FacilityLocationSnapshot


@dataclass(frozen=True, slots=True)
class ContractOfferSnapshot:
    """Typed immutable projection produced before JSON persistence."""

    id: str
    market_model: str
    cargo_system: str
    origin: FacilityLocationSnapshot
    destination: FacilityLocationSnapshot
    shipper_name: str
    consignee_name: str
    cargo: CargoProfile
    origin_cargo_evidence: CargoProfile
    destination_cargo_evidence: CargoProfile
    cargo_basis: str
    trade_match_type: str
    tons: float
    payload_band: str
    rate_eur_per_km_ton: float
    created_at: float
    expires_at: float
    mode: str
    relationship_simulated: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize the typed offer without expanding reference aggregates."""
        origin = self.origin.to_dict()
        destination = self.destination.to_dict()
        origin_evidence = asdict(self.origin_cargo_evidence)
        return {
            "id": self.id,
            "market_model": self.market_model,
            "cargo_system": self.cargo_system,
            "origin_hub_id": self.origin.facility_uid,
            "destination_hub_id": self.destination.facility_uid,
            "origin_facility_uid": self.origin.facility_uid,
            "destination_facility_uid": self.destination.facility_uid,
            "origin": origin,
            "destination": destination,
            "shipper_name": self.shipper_name,
            "consignee_name": self.consignee_name,
            "cargo": self.cargo.name,
            "cargo_code": self.cargo.code,
            "cargo_evidence": origin_evidence,
            "origin_cargo_evidence": origin_evidence,
            "destination_cargo_evidence": asdict(
                self.destination_cargo_evidence
            ),
            "cargo_basis": self.cargo_basis,
            "trade_match_type": self.trade_match_type,
            "tons": self.tons,
            "payload_band": self.payload_band,
            "rate_eur_per_km_ton": self.rate_eur_per_km_ton,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "mode": self.mode,
            "relationship_simulated": self.relationship_simulated,
        }
