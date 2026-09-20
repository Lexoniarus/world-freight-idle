"""Explicit player-state upgrade, preserving all monetary and trip values."""

import copy
import logging
from typing import Any

from app.domain.ports import WorldCatalogue, WorldStateStore
from app.domain.world import WorldSnapshot

LOGGER = logging.getLogger(__name__)


class WorldStateMigrationService:
    """Resolve stable reference identities before an atomic state rewrite."""

    def __init__(
        self,
        world: WorldCatalogue,
        repository: WorldStateStore,
    ) -> None:
        self.world = world
        self.repository = repository

    def migrate(self) -> int:
        """Migrate only after the caller has created a consistent backup."""
        world = self.world.read()

        def convert(records: dict[str, Any]) -> dict[str, Any]:
            """Bind the single reference revision to the state transaction."""
            return migrate_world_records(records, world)

        try:
            changed = self.repository.transform(convert)
        except Exception:
            LOGGER.exception(
                "World player-state migration rolled back",
                extra={"event": "world.state_migration_failed"},
            )
            raise
        LOGGER.info(
            "World player-state migration completed",
            extra={
                "event": "world.state_migrated",
                "data": {
                    "changed_keys": changed,
                    "catalogue_version": world.version,
                },
            },
        )
        return changed


def endpoint_snapshot(identifier: str, world: WorldSnapshot) -> dict[str, Any]:
    """Require explicit routable identity matches; never relocate a vehicle."""
    facility = world.get_facility(identifier)
    if not facility.is_routable():
        raise ValueError("Unroutable migration endpoint")
    return facility.to_dict()


def migrate_contract(contract: dict[str, Any], world: WorldSnapshot) -> None:
    """Add endpoint facts and preserve legacy commercial terms."""
    for side in ("origin", "destination"):
        if f"{side}_facility_uid" not in contract:
            snapshot = endpoint_snapshot(contract[f"{side}_hub_id"], world)
            contract[side] = snapshot
            contract[f"{side}_facility_uid"] = snapshot["facility_uid"]
            contract[f"{side}_hub_id"] = snapshot["facility_uid"]
    contract.setdefault("relationship_simulated", True)


def migrate_world_records(
    records: dict[str, Any],
    world: WorldSnapshot,
) -> dict[str, Any]:
    """Upgrade JSON copies without altering original trip payloads."""
    for key, value in records.items():
        if key.rsplit(":", 1)[-1] == "world_state_version" and value != 1:
            raise ValueError("Unsupported player world-state version")
    result = copy.deepcopy(records)
    for key, value in list(result.items()):
        kind = key.rsplit(":", 1)[-1]
        if kind == "vehicles":
            for vehicle in value:
                if "location_snapshot" not in vehicle:
                    snapshot = endpoint_snapshot(vehicle["hub_id"], world)
                    vehicle.update(
                        facility_uid=snapshot["facility_uid"],
                        hub_id=snapshot["facility_uid"],
                        location_snapshot=snapshot,
                    )
        elif kind == "contracts":
            for contract in value:
                migrate_contract(contract, world)
        elif kind in {"active_trips", "active_trip"}:
            trips = (
                value if kind == "active_trips" else [value] if value else []
            )
            for trip in trips:
                migrate_contract(trip["contract"], world)
                for side in ("origin", "destination"):
                    trip.setdefault(
                        f"{side}_snapshot",
                        preserve_routing_endpoint(
                            trip["contract"][side],
                            trip.get(side),
                        ),
                    )
        else:
            continue
        prefix = key[: -len(kind)]
        result[prefix + "world_state_version"] = 1
    return result


def preserve_routing_endpoint(
    snapshot: dict[str, Any],
    historical: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep saved routing points explicit without claiming new verification."""
    result = copy.deepcopy(snapshot)
    if historical:
        result["legacy_endpoint"] = copy.deepcopy(historical)
        for key in ("lat", "lon", "address", "label"):
            if key in historical:
                result[key] = historical[key]
        if (result["lat"], result["lon"]) != (
            snapshot["lat"],
            snapshot["lon"],
        ):
            result["coordinate_evidence"] = []
            result["geocoding_status"] = "legacy_transport_snapshot"
    return result
