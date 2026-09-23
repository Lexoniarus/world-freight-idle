"""Immutable runtime contract snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.validation import require_finite, require_identity
from app.domain.world import FacilityLocationSnapshot


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
    cargo: NhmProduct
    origin_cargo_evidence: FacilityNhmProfile
    destination_cargo_evidence: FacilityNhmProfile
    cargo_basis: str
    trade_match_type: str
    tons: float
    payload_band: str
    rate_eur_per_km_ton: float
    created_at: float
    expires_at: float
    mode: str
    relationship_simulated: bool


@dataclass(frozen=True, slots=True)
class ContractOffer:
    """Available freight offer with stable identity and lifecycle rules."""

    id: str
    market_model: str
    cargo_system: str
    origin: FacilityLocationSnapshot
    destination: FacilityLocationSnapshot
    shipper_name: str
    consignee_name: str
    cargo: NhmProduct
    origin_cargo_evidence: FacilityNhmProfile
    destination_cargo_evidence: FacilityNhmProfile
    cargo_basis: str
    trade_match_type: str
    tons: float
    payload_band: str
    rate_eur_per_km_ton: float
    created_at: float
    expires_at: float
    mode: str
    relationship_simulated: bool

    def __post_init__(self) -> None:
        """Reject invalid offer terms before an offer enters a use case."""
        require_identity(self.id, "Contract ID")
        require_identity(self.market_model, "Market model")
        require_finite(self.tons, "Tonnage", 0.01)
        require_finite(self.rate_eur_per_km_ton, "Freight rate")
        require_finite(self.created_at, "Creation time")
        require_finite(self.expires_at, "Expiry time")
        if self.expires_at <= self.created_at:
            raise ValueError("Expiry must follow creation.")
        if self.origin.facility_uid == self.destination.facility_uid:
            raise ValueError("Contract endpoints must differ.")
        if self.cargo.code not in {
            self.origin_cargo_evidence.product.code,
            self.destination_cargo_evidence.product.code,
        }:
            raise ValueError("Cargo code does not match contract evidence.")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ContractOfferSnapshot,
    ) -> ContractOffer:
        """Promote generated immutable facts to a game-domain offer."""
        return cls(
            id=snapshot.id,
            market_model=snapshot.market_model,
            cargo_system=snapshot.cargo_system,
            origin=snapshot.origin,
            destination=snapshot.destination,
            shipper_name=snapshot.shipper_name,
            consignee_name=snapshot.consignee_name,
            cargo=snapshot.cargo,
            origin_cargo_evidence=snapshot.origin_cargo_evidence,
            destination_cargo_evidence=snapshot.destination_cargo_evidence,
            cargo_basis=snapshot.cargo_basis,
            trade_match_type=snapshot.trade_match_type,
            tons=snapshot.tons,
            payload_band=snapshot.payload_band,
            rate_eur_per_km_ton=snapshot.rate_eur_per_km_ton,
            created_at=snapshot.created_at,
            expires_at=snapshot.expires_at,
            mode=snapshot.mode,
            relationship_simulated=snapshot.relationship_simulated,
        )

    def is_available(self, now: float, market_model: str) -> bool:
        """Require the current market model and a non-expired offer."""
        require_finite(now, "Current time")
        return (
            self.market_model == market_model
            and self.created_at <= now < self.expires_at
        )
