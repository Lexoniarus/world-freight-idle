"""SQLite scalar projections that leave road geometry out of polling."""

import json
from typing import Any

from app.domain.errors import PersistenceError
from app.domain.read_ports import SharedTransport, TrafficReader
from app.domain.runtime_views import (
    GeometrySpan,
    RuntimeSnapshot,
    RuntimeTransport,
    TransportGeometry,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import (
    SqliteGameStateRepository,
    load_transport_record,
)
from app.repositories.snapshot_mapping import (
    load_historical_contract,
    load_location,
)
from app.repositories.transport_mapping import (
    load_cost_breakdown,
    load_journey,
    validate_transport_envelope,
)

PRIVATE_PATHS = {
    "contract": "contract",
    "origin": "origin",
    "destination": "destination",
    "start": "dispatch_route.start",
    "journey": "journey",
    "distance_km": "route.distance_km",
    "routing_duration_seconds": "route.duration_seconds",
    "provider": "route.provider",
    "cost_breakdown": "cost_breakdown",
    "approach_distance_km": "dispatch_route.approach.distance_km",
    "snapshot_id": "id",
    "snapshot_vehicle_id": "vehicle_id",
    "snapshot_departed_at": "departed_at",
    "snapshot_arrives_at": "arrives_at",
    "snapshot_payout_eur": "payout_eur",
    "snapshot_operating_cost_eur": "operating_cost_eur",
}
PRIVATE_COLUMNS = ", ".join(
    f"json_extract(transport_snapshot, '$.data.{path}') AS {name}"
    for name, path in PRIVATE_PATHS.items()
)


class SqliteRuntimeReader:
    """Project bounded current data through the canonical relational store."""

    def __init__(
        self,
        database: SqliteGameDatabase,
        traffic: TrafficReader,
    ) -> None:
        """Share transaction ownership, never a second persistence format."""
        self.database = database
        self.public_traffic = traffic

    def read(self, user_id: str) -> RuntimeSnapshot:
        """Load private active summaries without selecting coordinate JSON."""
        repository = SqliteGameStateRepository(self.database, user_id)
        with self.database.read_transaction(), self.database.connect() as db:
            player = repository.get_player()
            if player is None:
                raise PersistenceError("Spielstand nicht initialisiert.")
            rows = db.execute(
                "SELECT transport_id, vehicle_id, departed_at, arrives_at, "
                "payout_eur, operating_cost_eur, origin_facility_uid, "
                "destination_facility_uid, contract_id, "
                "json_extract(transport_snapshot, '$.version') AS version, "
                "json_extract(transport_snapshot, '$.kind') AS kind, "
                + PRIVATE_COLUMNS
                + " FROM transports WHERE user_id=? "
                "AND status='active' ORDER BY rowid",
                (user_id,),
            ).fetchall()
            return RuntimeSnapshot(
                player,
                repository.list_vehicles(),
                tuple(load_runtime_transport(dict(row)) for row in rows),
            )

    def traffic(self, now: float) -> tuple[SharedTransport, ...]:
        """Delegate public scalar selection to its canonical shared owner."""
        return self.public_traffic.list_active_summaries(now)

    def visible(
        self, owner_id: str, trip_id: str, viewer_id: str, now: float
    ) -> bool:
        """Recheck authorization even for conditional geometry requests."""
        with self.database.connect() as db:
            return (
                db.execute(
                    "SELECT 1 FROM transports "
                    "WHERE user_id=? AND transport_id=? "
                    "AND (user_id=? OR (status='active' AND arrives_at>?))",
                    (owner_id, trip_id, viewer_id, now),
                ).fetchone()
                is not None
            )

    def geometry(self, owner_id: str, trip_id: str) -> TransportGeometry:
        """Load exactly one requested historical route and its leg indices."""
        with self.database.connect() as db:
            row = db.execute(
                "SELECT * FROM transports WHERE user_id=? AND transport_id=?",
                (owner_id, trip_id),
            ).fetchone()
        if row is None:
            raise KeyError("Route not found.")
        trip = load_transport_record(dict(row))
        spans = []
        if trip.dispatch_route is not None:
            offset = 0
            for leg in trip.dispatch_route.legs:
                spans.append(
                    GeometrySpan(
                        leg.purpose,
                        offset,
                        offset + len(leg.coordinates),
                        leg.start_km,
                        leg.end_km,
                        leg.routing_duration_seconds,
                    )
                )
                offset += len(leg.coordinates)
                approach = trip.dispatch_route.approach
                if leg.purpose == "approach" and approach is not None:
                    offset -= int(
                        approach.coordinates[-1]
                        == trip.dispatch_route.delivery.coordinates[0]
                    )
        return TransportGeometry(trip.route.coordinates, tuple(spans))


def load_runtime_transport(row: dict[str, Any]) -> RuntimeTransport:
    """Validate indexed identities against the compact canonical document."""
    try:
        validate_transport_envelope(row)
        for key in (
            "vehicle_id",
            "departed_at",
            "arrives_at",
            "payout_eur",
            "operating_cost_eur",
        ):
            if row[key] != row["snapshot_" + key]:
                raise ValueError("Transport columns differ.")
        origin = load_location(json.loads(row["origin"]))
        destination = load_location(json.loads(row["destination"]))
        contract = load_historical_contract(json.loads(row["contract"]))
        if (
            row["transport_id"] != row["snapshot_id"]
            or row["contract_id"] != contract.id
            or row["origin_facility_uid"] != origin.facility_uid
            or row["destination_facility_uid"] != destination.facility_uid
        ):
            raise ValueError("Transport identities differ.")
        return RuntimeTransport(
            row["transport_id"],
            row["vehicle_id"],
            contract,
            origin,
            destination,
            load_location(json.loads(row["start"]))
            if row["start"]
            else origin,
            load_journey(json.loads(row["journey"])),
            row["distance_km"],
            row["routing_duration_seconds"],
            row["provider"],
            row["approach_distance_km"] or 0,
            row["departed_at"],
            row["arrives_at"],
            row["payout_eur"],
            row["operating_cost_eur"],
            load_cost_breakdown(json.loads(row["cost_breakdown"]))
            if row["cost_breakdown"]
            else None,
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise PersistenceError("Transportdaten nicht lesbar.") from exc
