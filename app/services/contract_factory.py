"""Create compact persisted contracts from precomputed trade options."""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from app.services.trade_network import TradeOption
from app.simulation import STANDARD_RATE, PayloadBand


@dataclass(slots=True)
class ContractFactory:
    """Snapshot one trade option without embedding the full world catalogue."""

    model_id: ClassVar[str] = "nhm_v1"
    cargo_system: ClassVar[str] = "NHM2026"

    rng: random.Random

    def build(
        self,
        option: TradeOption,
        now: float,
        band: PayloadBand,
    ) -> dict[str, Any]:
        """Create one immutable simulated commercial contract."""
        origin = option.origin
        destination = option.destination
        cargo_basis = (
            "derived"
            if option.origin_cargo.evidence_type == "derived"
            else "documented"
        )
        return {
            "id": str(uuid.UUID(int=self.rng.getrandbits(128))),
            "market_model": self.model_id,
            "cargo_system": self.cargo_system,
            "origin_hub_id": origin.facility_uid,
            "destination_hub_id": destination.facility_uid,
            "origin_facility_uid": origin.facility_uid,
            "destination_facility_uid": destination.facility_uid,
            "origin": origin.location_snapshot(),
            "destination": destination.location_snapshot(),
            "shipper_name": (
                origin.company.display_name if origin.company else origin.label
            ),
            "consignee_name": (
                destination.company.display_name
                if destination.company
                else destination.label
            ),
            "cargo": option.cargo.name,
            "cargo_code": option.cargo.code,
            "cargo_evidence": asdict(option.origin_cargo),
            "origin_cargo_evidence": asdict(option.origin_cargo),
            "destination_cargo_evidence": asdict(option.destination_cargo),
            "cargo_basis": cargo_basis,
            "trade_match_type": option.match_type,
            "tons": max(
                0.01,
                math.floor(
                    self.rng.uniform(0.6, 1.0) * band.maximum_tons * 100
                )
                / 100,
            ),
            "payload_band": band.name,
            "rate_eur_per_km_ton": STANDARD_RATE,
            "created_at": now,
            "expires_at": now + 6 * 3600,
            "mode": "truck",
            "relationship_simulated": True,
        }
