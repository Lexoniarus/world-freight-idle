"""Simulated contracts between evidenced public facilities."""

import math
import random
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from app.domain.errors import WorldCatalogueError
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.world import Facility
from app.simulation import STANDARD_RATE, PayloadBand, build_payload_bands


@dataclass(slots=True)
class MarketGenerator:
    """Offer work at every verified endpoint with simulated fallback."""

    world: WorldCatalogue
    rng: random.Random
    vehicles: VehicleCatalogue

    def generate(
        self,
        now: float,
        origin_hub_ids: list[str],
        contract_count: int = 6,
        existing_contracts: list[dict[str, Any]] | None = None,
        owned_capacities: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Prioritize trucks; require onward work at every destination."""
        snapshot = self.world.read()
        candidates = tuple(f for f in snapshot.facilities if f.is_routable())
        if len(candidates) < 2:
            raise WorldCatalogueError("Zu wenige geeignete Frachtstandorte.")
        retained = list(existing_contracts or [])
        bands = build_payload_bands(
            [model.capacity_tons for model in self.vehicles.list_models()]
            + list(owned_capacities or [])
        )
        available = {f.facility_uid: f for f in candidates}
        origins = []
        planned: set[str] = set()
        for identifier in origin_hub_ids:
            try:
                facility = snapshot.get_facility(identifier)
            except KeyError:
                continue
            if (
                facility.facility_uid in available
                and facility.facility_uid not in planned
            ):
                origins.append(facility)
                planned.add(facility.facility_uid)
        origins.extend(f for f in candidates if f.facility_uid not in planned)
        contracts = list(retained)
        for origin in origins:
            for band in bands:
                if not any(
                    item["origin_hub_id"] == origin.facility_uid
                    and item.get("payload_band") == band.name
                    and 0 < item["tons"] <= band.maximum_tons
                    for item in retained
                ):
                    contracts.append(
                        self._build_contract(origin, candidates, now, band)
                    )
        while len(contracts) < contract_count:
            contracts.append(
                self._build_contract(
                    self.rng.choice(candidates),
                    candidates,
                    now,
                    self.rng.choice(bands),
                )
            )
        return contracts

    def _build_contract(
        self,
        origin: Facility,
        candidates: tuple[Facility, ...],
        now: float,
        band: PayloadBand,
    ) -> dict[str, Any]:
        """Snapshot facts and label the commercial relation simulated."""
        destination = self.rng.choice(
            tuple(
                f for f in candidates if f.facility_uid != origin.facility_uid
            )
        )
        documented = origin.outbound_cargo()
        cargo = self.rng.choice(documented) if documented else None
        return {
            "id": str(uuid.UUID(int=self.rng.getrandbits(128))),
            "origin_hub_id": origin.facility_uid,
            "destination_hub_id": destination.facility_uid,
            "origin_facility_uid": origin.facility_uid,
            "destination_facility_uid": destination.facility_uid,
            "origin": origin.to_dict(),
            "destination": destination.to_dict(),
            "shipper_name": origin.company.display_name
            if origin.company
            else origin.label,
            "consignee_name": destination.company.display_name
            if destination.company
            else destination.label,
            "cargo": cargo.name if cargo else "Standardfracht (Simulation)",
            "cargo_code": cargo.code if cargo else "simulated_standard",
            "cargo_evidence": asdict(cargo) if cargo else None,
            "cargo_basis": "documented" if cargo else "simulated",
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
