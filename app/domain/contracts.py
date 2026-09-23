"""Immutable runtime contract snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.domain.validation import require_finite, require_identity
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
        origin_evidence["ancestor_row_ids"] = list(
            self.origin_cargo_evidence.ancestor_row_ids
        )
        destination_evidence = asdict(self.destination_cargo_evidence)
        destination_evidence["ancestor_row_ids"] = list(
            self.destination_cargo_evidence.ancestor_row_ids
        )
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
            "destination_cargo_evidence": destination_evidence,
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
            self.origin_cargo_evidence.code,
            self.destination_cargo_evidence.code,
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

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContractOffer:
        """Hydrate one persisted current-model contract offer."""
        origin_cargo = CargoProfile.from_dict(value["origin_cargo_evidence"])
        destination_cargo = CargoProfile.from_dict(
            value["destination_cargo_evidence"]
        )
        cargo_code = str(value["cargo_code"])
        if origin_cargo.code == cargo_code:
            cargo = origin_cargo
        elif destination_cargo.code == cargo_code:
            cargo = destination_cargo
        else:
            raise ValueError("Cargo code does not match contract evidence.")
        return cls(
            id=str(value["id"]),
            market_model=str(value["market_model"]),
            cargo_system=str(value["cargo_system"]),
            origin=FacilityLocationSnapshot.from_dict(value["origin"]),
            destination=FacilityLocationSnapshot.from_dict(
                value["destination"]
            ),
            shipper_name=str(value["shipper_name"]),
            consignee_name=str(value["consignee_name"]),
            cargo=cargo,
            origin_cargo_evidence=origin_cargo,
            destination_cargo_evidence=destination_cargo,
            cargo_basis=str(value["cargo_basis"]),
            trade_match_type=str(value["trade_match_type"]),
            tons=value["tons"],
            payload_band=str(value["payload_band"]),
            rate_eur_per_km_ton=value["rate_eur_per_km_ton"],
            created_at=value["created_at"],
            expires_at=value["expires_at"],
            mode=str(value["mode"]),
            relationship_simulated=bool(value["relationship_simulated"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the stable public and persistence projection."""
        return ContractOfferSnapshot(
            id=self.id,
            market_model=self.market_model,
            cargo_system=self.cargo_system,
            origin=self.origin,
            destination=self.destination,
            shipper_name=self.shipper_name,
            consignee_name=self.consignee_name,
            cargo=self.cargo,
            origin_cargo_evidence=self.origin_cargo_evidence,
            destination_cargo_evidence=self.destination_cargo_evidence,
            cargo_basis=self.cargo_basis,
            trade_match_type=self.trade_match_type,
            tons=self.tons,
            payload_band=self.payload_band,
            rate_eur_per_km_ton=self.rate_eur_per_km_ton,
            created_at=self.created_at,
            expires_at=self.expires_at,
            mode=self.mode,
            relationship_simulated=self.relationship_simulated,
        ).to_dict()

    def is_available(self, now: float, market_model: str) -> bool:
        """Require the current market model and a non-expired offer."""
        require_finite(now, "Current time")
        return (
            self.market_model == market_model
            and self.created_at <= now < self.expires_at
        )
