"""Fictional contract generation over real freight addresses."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass

from app.domain.models import CargoType, Contract, Hub


@dataclass(slots=True)
class MarketGenerator:
    """Generate fictional jobs while preserving real geographic endpoints."""

    hubs: tuple[Hub, ...]
    cargo_types: tuple[CargoType, ...]
    shipper_names: tuple[str, ...]
    consignee_names: tuple[str, ...]
    rng: random.Random

    def generate(
        self,
        now: float,
        origin_hub_ids: list[str],
        contract_count: int = 6,
    ) -> list[dict]:
        """Create a market with guaranteed work at idle vehicle origins."""
        if not self.hubs:
            return []
        origins = list(origin_hub_ids)
        while len(origins) < contract_count:
            origins.append(self.rng.choice(self.hubs).id)

        contracts = [
            self._build_contract(origin_id, now).to_dict()
            for origin_id in origins[:contract_count]
        ]
        return contracts

    def _build_contract(self, origin_hub_id: str, now: float) -> Contract:
        """Create one contract from an origin to a different real hub."""
        destinations = [hub for hub in self.hubs if hub.id != origin_hub_id]
        destination = self.rng.choice(destinations)
        cargo = self.rng.choice(self.cargo_types)
        tons = round(
            self.rng.uniform(
                cargo.min_tons,
                min(cargo.max_tons, 24.0),
            ),
            1,
        )
        return Contract(
            id=str(uuid.UUID(int=self.rng.getrandbits(128))),
            origin_hub_id=origin_hub_id,
            destination_hub_id=destination.id,
            shipper_name=self.rng.choice(self.shipper_names),
            consignee_name=self.rng.choice(self.consignee_names),
            cargo=cargo.name,
            tons=tons,
            created_at=now,
            expires_at=now + 6 * 3600,
        )
