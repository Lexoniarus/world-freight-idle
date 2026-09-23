"""Explicit offline upgrade of relational 1.0.0 state into a new file."""

import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.domain.errors import PersistenceError
from app.domain.game import PlayerState
from app.domain.journeys import unmetered_journey
from app.domain.vehicles import VehicleModel
from app.repositories.game_database import (
    SqliteGameDatabase,
    schema_sql_tokens,
)
from app.repositories.game_schema import REQUIRED_TABLES, SCHEMA
from app.repositories.game_state import (
    load_offer_record,
    load_transport_record,
    load_vehicle_record,
)
from app.repositories.state_snapshots import encode_snapshot

LOGGER = logging.getLogger(__name__)
ENERGY_COLUMNS = (
    "    energy_snapshot TEXT NOT NULL,\n"
    "    energy_level REAL NOT NULL CHECK(energy_level >= 0),\n"
    "    top_speed_kmh REAL NOT NULL CHECK(top_speed_kmh > 0),\n"
)
SOURCE_SCHEMA = SCHEMA.replace(ENERGY_COLUMNS, "").replace("1.1.0", "1.0.0")
EXTRA_TABLES = {
    "sessions",
    "auth_attempts",
    "geocode_cache",
    "route_cache",
}


@dataclass(frozen=True)
class EnergyUpgradeInventory:
    """Private source records; public reports contain counts only."""

    tables: dict[str, tuple[dict[str, Any], ...]] = field(repr=False)
    extra_schema: tuple[str, ...] = field(repr=False)


class VehicleEnergyUpgradeRepository:
    """Validate and copy a read-only source without touching active state."""

    def __init__(self, source: Path, models: tuple[VehicleModel, ...]) -> None:
        self.source = source.resolve()
        self.models = {model.id: model for model in models}

    def inspect(self) -> dict[str, int]:
        """Validate every source record using the same rules as execution."""
        inventory = self._read_source()
        for table, rows in inventory.tables.items():
            for row in rows:
                self._convert_record(table, row)
        return {
            "accounts": len(inventory.tables["users"]),
            "vehicles": len(inventory.tables["owned_vehicles"]),
            "transports": len(inventory.tables["transports"]),
            "sessions": len(inventory.tables.get("sessions", ())),
        }

    def upgrade_to(self, target: Path) -> dict[str, int]:
        """Create and reconcile a new file; remove failed output."""
        inventory = self._read_source()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb"):
            pass
        try:
            database = SqliteGameDatabase(target)
            database.initialize()
            self._write_inventory(database, inventory)
            self._verify_inventory(database, inventory)
            database.initialize()
        except BaseException:
            target.unlink(missing_ok=True)
            LOGGER.error(
                "Vehicle energy upgrade rolled back",
                extra={"event": "state.energy_upgrade_rolled_back"},
            )
            raise
        counts = {
            "accounts": len(inventory.tables["users"]),
            "vehicles": len(inventory.tables["owned_vehicles"]),
            "transports": len(inventory.tables["transports"]),
            "sessions": len(inventory.tables.get("sessions", ())),
        }
        LOGGER.info(
            "Vehicle energy upgrade reconciled",
            extra={
                "event": "state.energy_upgraded",
                "data": {
                    **counts,
                    "source_version": "1.0.0",
                    "target_version": "1.1.0",
                },
            },
        )
        return counts

    def _read_source(self) -> EnergyUpgradeInventory:
        """Read a consistent inventory; reject unknown or corrupt schemas."""
        try:
            with closing(
                sqlite3.connect(self.source.as_uri() + "?mode=ro", uri=True)
            ) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                if [
                    tuple(row) for row in db.execute("PRAGMA integrity_check")
                ] != [("ok",)] or db.execute(
                    "PRAGMA foreign_key_check"
                ).fetchone():
                    raise ValueError("Source integrity differs.")
                self._validate_source_schema(db)
                schemas = db.execute(
                    "SELECT name, sql FROM sqlite_master "
                    "WHERE type='table' ORDER BY name"
                ).fetchall()
                tables = {
                    name: tuple(
                        dict(row)
                        for row in db.execute(
                            f'SELECT * FROM "{name}" ORDER BY rowid'
                        )
                    )
                    for name, _ in schemas
                }
                extra_schema = tuple(
                    sql for name, sql in schemas if name in EXTRA_TABLES
                )
                extra_schema += tuple(
                    row[0]
                    for row in db.execute(
                        "SELECT sql FROM sqlite_master WHERE type='index' "
                        "AND sql IS NOT NULL AND tbl_name IN "
                        "('sessions','auth_attempts',"
                        "'geocode_cache','route_cache')"
                    )
                )
                return EnergyUpgradeInventory(tables, extra_schema)
        except (sqlite3.Error, ValueError) as exc:
            LOGGER.error(
                "Vehicle energy upgrade rejected",
                extra={"event": "state.energy_upgrade_rejected"},
            )
            raise PersistenceError(
                "Energieübernahme: Quellschema oder Daten beschädigt."
            ) from exc

    def _validate_source_schema(self, db: sqlite3.Connection) -> None:
        """Require the exact supported old core and known auxiliary tables."""
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not REQUIRED_TABLES <= tables or tables - (
            REQUIRED_TABLES | EXTRA_TABLES
        ):
            raise ValueError("Unsupported source tables.")
        if [
            tuple(row) for row in db.execute("SELECT version FROM game_schema")
        ] != [("1.0.0",)]:
            raise ValueError("Source is not schema 1.0.0.")
        with closing(sqlite3.connect(":memory:")) as reference:
            reference.executescript(SOURCE_SCHEMA)
            for name, expected in reference.execute(
                "SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL"
            ):
                actual = db.execute(
                    "SELECT sql FROM sqlite_master WHERE name=?", (name,)
                ).fetchone()
                if actual is None or schema_sql_tokens(actual[0]) != (
                    schema_sql_tokens(expected)
                ):
                    raise ValueError("Source safeguards differ.")

    def _convert_record(self, table: str, row: dict) -> dict:
        """Add only energy facts; validate existing domain values unchanged."""
        value = dict(row)
        try:
            if table == "owned_vehicles":
                model = self.models[value["model_id"]]
                value.update(
                    energy_snapshot=encode_snapshot(
                        "energy", asdict(model.energy)
                    ),
                    energy_level=model.energy.capacity,
                    top_speed_kmh=model.top_speed_kmh,
                )
                load_vehicle_record(value)
            elif table == "transports":
                document = json.loads(value["transport_snapshot"])
                if (
                    not isinstance(document, dict)
                    or document.keys() != {"version", "kind", "data"}
                    or type(document["version"]) is not int
                    or document["version"] != 1
                    or document["kind"] != "transport"
                    or not isinstance(document["data"], dict)
                    or "journey" in document["data"]
                ):
                    raise ValueError("Unsupported source transport.")
                data = document["data"]
                data["journey"] = asdict(
                    unmetered_journey(
                        data["route"]["distance_km"],
                        data["arrives_at"] - data["departed_at"],
                    )
                )
                value["transport_snapshot"] = encode_snapshot(
                    "transport", data
                )
                load_transport_record(value)
            elif table == "contract_offers":
                load_offer_record(value)
            elif table == "player_states":
                PlayerState(
                    value["cash"], value["completed"], value["reputation"]
                )
            return value
        except (KeyError, TypeError, ValueError) as exc:
            raise PersistenceError(
                "Energieübernahme: unbekanntes Modell oder ungültige Werte."
            ) from exc

    def _write_inventory(
        self, database: SqliteGameDatabase, inventory: EnergyUpgradeInventory
    ) -> None:
        """Write the validated source with new snapshots in one transaction."""
        with database.transaction(), database.connect() as db:
            for statement in inventory.extra_schema:
                db.execute(statement)
            for table in (
                "users",
                "player_states",
                "owned_vehicles",
                "contract_offers",
                "transports",
                *sorted(EXTRA_TABLES),
            ):
                for row in inventory.tables.get(table, ()):
                    value = self._convert_record(table, row)
                    columns = ",".join('"' + name + '"' for name in value)
                    placeholders = ",".join("?" for _ in value)
                    db.execute(
                        f'INSERT INTO "{table}" ({columns}) '
                        f"VALUES ({placeholders})",
                        tuple(value.values()),
                    )

    def _verify_inventory(
        self, database: SqliteGameDatabase, inventory: EnergyUpgradeInventory
    ) -> None:
        """Compare all source values and the documented additions."""
        with database.connect() as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise PersistenceError("Energieübernahme: Integritätsfehler.")
            if db.execute("PRAGMA foreign_key_check").fetchone():
                raise PersistenceError("Energieübernahme: Besitzfehler.")
            for table, rows in inventory.tables.items():
                if table == "game_schema":
                    continue
                actual = tuple(
                    dict(row)
                    for row in db.execute(
                        f'SELECT * FROM "{table}" ORDER BY rowid'
                    )
                )
                expected = tuple(
                    self._convert_record(table, row) for row in rows
                )
                if actual != expected:
                    raise PersistenceError(
                        "Energieübernahme: Abgleich fehlgeschlagen."
                    )
