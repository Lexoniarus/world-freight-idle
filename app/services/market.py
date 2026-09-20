"""Simulated NHM contracts between evidenced public facilities."""

import math
import random
import uuid
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from app.domain.errors import WorldCatalogueError
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.world import CargoProfile, Facility
from app.simulation import STANDARD_RATE, PayloadBand, build_payload_bands

InboundEntry = tuple[Facility, CargoProfile]
InboundIndex = dict[int, tuple[InboundEntry, ...]]


@dataclass(frozen=True, slots=True)
class TradeOption:
    """One compatible origin/destination NHM relation."""

    origin: Facility
    origin_cargo: CargoProfile
    destination: Facility
    destination_cargo: CargoProfile
    cargo: CargoProfile
    match_type: str


@dataclass(slots=True)
class MarketGenerator:
    """Generate NHM-based work at every routable public facility."""

    model_id: ClassVar[str] = "nhm_v1"
    cargo_system: ClassVar[str] = "NHM2026"

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
        """Guarantee work per facility and payload band using NHM matches."""
        snapshot = self.world.read()
        candidates = tuple(
            facility
            for facility in snapshot.facilities
            if facility.is_routable()
        )
        if len(candidates) < 2:
            raise WorldCatalogueError("Zu wenige geeignete Frachtstandorte.")
        retained = list(existing_contracts or [])
        bands = build_payload_bands(
            [model.capacity_tons for model in self.vehicles.list_models()]
            + list(owned_capacities or [])
        )
        available = {f.facility_uid: f for f in candidates}
        origins: list[Facility] = []
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
        origins.extend(
            facility
            for facility in candidates
            if facility.facility_uid not in planned
        )

        inbound_by_row, inbound_by_ancestor = self._index_inbound_cargo(
            candidates
        )
        trade_options = {
            origin.facility_uid: self._build_trade_options(
                origin,
                inbound_by_row,
                inbound_by_ancestor,
            )
            for origin in origins
        }
        contracts = list(retained)
        for origin in origins:
            options = trade_options[origin.facility_uid]
            for band in bands:
                if not any(
                    item["origin_hub_id"] == origin.facility_uid
                    and item.get("payload_band") == band.name
                    and 0 < item["tons"] <= band.maximum_tons
                    for item in retained
                ):
                    contracts.append(
                        self._build_contract(
                            self._select_trade_option(options),
                            now,
                            band,
                        )
                    )
        while len(contracts) < contract_count:
            origin = self.rng.choice(origins)
            contracts.append(
                self._build_contract(
                    self._select_trade_option(
                        trade_options[origin.facility_uid]
                    ),
                    now,
                    self.rng.choice(bands),
                )
            )
        return contracts

    def _index_inbound_cargo(
        self,
        candidates: tuple[Facility, ...],
    ) -> tuple[InboundIndex, InboundIndex]:
        """Index inbound profiles by exact NHM node and every ancestor."""
        by_row: dict[int, list[InboundEntry]] = {}
        by_ancestor: dict[int, list[InboundEntry]] = {}
        for facility in candidates:
            for profile in facility.inbound_cargo():
                entry = (facility, profile)
                by_row.setdefault(profile.nhm_row_id, []).append(entry)
                for ancestor_row_id in profile.ancestor_row_ids:
                    by_ancestor.setdefault(ancestor_row_id, []).append(entry)
        return (
            {key: tuple(value) for key, value in by_row.items()},
            {key: tuple(value) for key, value in by_ancestor.items()},
        )

    def _build_trade_options(
        self,
        origin: Facility,
        inbound_by_row: InboundIndex,
        inbound_by_ancestor: InboundIndex,
    ) -> tuple[TradeOption, ...]:
        """Build all compatible NHM trades from one origin facility."""
        options: list[TradeOption] = []
        seen: set[tuple[int, str, int]] = set()
        for origin_cargo in origin.outbound_cargo():
            matches = list(
                inbound_by_ancestor.get(origin_cargo.nhm_row_id, ())
            )
            for ancestor_row_id in origin_cargo.ancestor_row_ids:
                matches.extend(inbound_by_row.get(ancestor_row_id, ()))
            for destination, destination_cargo in matches:
                if destination.facility_uid == origin.facility_uid:
                    continue
                key = (
                    origin_cargo.nhm_row_id,
                    destination.facility_uid,
                    destination_cargo.nhm_row_id,
                )
                if key in seen:
                    continue
                seen.add(key)
                cargo = max(
                    (origin_cargo, destination_cargo),
                    key=lambda item: len(item.ancestor_row_ids),
                )
                match_type = (
                    "exact"
                    if origin_cargo.nhm_row_id == destination_cargo.nhm_row_id
                    else "ancestor"
                )
                options.append(
                    TradeOption(
                        origin,
                        origin_cargo,
                        destination,
                        destination_cargo,
                        cargo,
                        match_type,
                    )
                )
        if not options:
            raise WorldCatalogueError(
                "Kein kompatibler NHM-Warenstrom für diesen Standort."
            )
        return tuple(options)

    def _select_trade_option(
        self,
        options: tuple[TradeOption, ...],
    ) -> TradeOption:
        """Prefer sourced, confident and exact NHM relations."""
        weights = []
        for option in options:
            origin_source = (
                1.45 if option.origin_cargo.evidence_type != "derived" else 1.0
            )
            destination_source = (
                1.25
                if option.destination_cargo.evidence_type != "derived"
                else 1.0
            )
            exact = 1.25 if option.match_type == "exact" else 1.0
            confidence = (
                0.5
                + option.origin_cargo.confidence
                + option.destination_cargo.confidence
            )
            priority = (
                0.5
                + option.origin_cargo.priority_score
                + option.destination_cargo.priority_score
            )
            weights.append(
                origin_source
                * destination_source
                * exact
                * confidence
                * priority
            )
        return self.rng.choices(options, weights=weights, k=1)[0]

    def _build_contract(
        self,
        option: TradeOption,
        now: float,
        band: PayloadBand,
    ) -> dict[str, Any]:
        """Snapshot one valid NHM trade as a simulated commercial contract."""
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
            "origin": origin.to_dict(),
            "destination": destination.to_dict(),
            "shipper_name": origin.company.display_name
            if origin.company
            else origin.label,
            "consignee_name": destination.company.display_name
            if destination.company
            else destination.label,
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
