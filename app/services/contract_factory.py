"""Create compact persisted contracts from precomputed trade options."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import ClassVar

from app.domain.contracts import ContractOfferSnapshot
from app.domain.market import MarketCandidate
from app.domain.market_calculations import shipment_tons
from app.domain.market_terms import OfferMarketContext
from app.simulation import STANDARD_RATE


@dataclass(slots=True)
class ContractFactory:
    """Snapshot one trade option without embedding the full world catalogue."""

    model_id: ClassVar[str] = "nhm_v2"
    cargo_system: ClassVar[str] = "NHM2026"

    rng: random.Random

    def build(
        self,
        candidate: MarketCandidate,
        now: float,
    ) -> ContractOfferSnapshot:
        """Create one typed immutable simulated contract snapshot."""
        option = candidate.trade
        selected = self.rng.choices(
            candidate.vehicles,
            weights=[v.suitability for v in candidate.vehicles],
            k=1,
        )[0].vehicle
        load = candidate.distance_profile
        tons = shipment_tons(
            selected.capacity_tons,
            self.rng.uniform(load.load_factor_min, load.load_factor_max),
        )
        profile = candidate.profile
        context = OfferMarketContext(
            load.distance_band,
            candidate.estimated_distance_km,
            profile.transport_class,
            selected.scale,
            selected.capacity_tons,
            profile.value_eur_per_t,
            round(tons * profile.value_eur_per_t),
        )
        origin = option.origin
        destination = option.destination
        cargo_basis = (
            "derived"
            if option.origin_cargo.evidence_type == "derived"
            else "documented"
        )
        return ContractOfferSnapshot(
            id=str(uuid.UUID(int=self.rng.getrandbits(128))),
            market_model=self.model_id,
            cargo_system=self.cargo_system,
            origin=origin.location_snapshot(),
            destination=destination.location_snapshot(),
            shipper_name=(
                origin.company.display_name if origin.company else origin.label
            ),
            consignee_name=(
                destination.company.display_name
                if destination.company
                else destination.label
            ),
            cargo=option.cargo,
            origin_cargo_evidence=option.origin_cargo,
            destination_cargo_evidence=option.destination_cargo,
            cargo_basis=cargo_basis,
            trade_match_type=option.match_type,
            tons=tons,
            payload_band="",
            market_context=context,
            rate_eur_per_km_ton=STANDARD_RATE
            * profile.freight_rate_factor_game,
            created_at=now,
            expires_at=now + 6 * 3600,
            mode="truck",
            relationship_simulated=True,
        )
