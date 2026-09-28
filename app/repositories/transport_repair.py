"""Offline normalization of a narrowly identified historical defect."""

import json
import logging
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.domain.errors import PersistenceError
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_schema import VERSION
from app.repositories.game_state import (
    load_transport_record,
    load_vehicle_record,
)
from app.repositories.snapshot_mapping import load_location
from app.repositories.state_snapshots import decode_snapshot, encode_snapshot

LOGGER = logging.getLogger(__name__)


def repaired_transport(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize only incomplete optional approach metadata."""
    try:
        load_transport_record(row)
        return row
    except PersistenceError:
        data = decode_snapshot("transport", row["transport_snapshot"])
        plan = data.get("dispatch_route")
        if not isinstance(plan, dict) or set(plan) != {
            "start",
            "pickup",
            "destination",
            "delivery",
            "approach",
        }:
            raise PersistenceError("Unbekannter Transportschaden.") from None
        try:
            load_location(plan["start"])
            known = (
                plan["approach"] is None
                and plan["start"]["facility_uid"]
                != plan["pickup"]["facility_uid"]
                and plan["start"]["city"] == plan["pickup"]["city"]
                and plan["pickup"] == data["origin"]
                and plan["destination"] == data["destination"]
                and plan["delivery"] == data["route"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PersistenceError("Unbekannter Transportschaden.") from exc
        if not known:
            raise PersistenceError("Unbekannter Transportschaden.") from None
        result = {
            **row,
            "transport_snapshot": encode_snapshot(
                "transport",
                {**data, "dispatch_route": None},
            ),
        }
        load_transport_record(result)
        return result


def table_digest(
    db: sqlite3.Connection,
    table: str,
    replacements: dict[tuple[str, str], dict[str, Any]],
) -> str:
    """Compare every persisted value and row identity without logging data."""
    quoted = '"' + table.replace('"', '""') + '"'
    digest = sha256()
    for row in db.execute(f"SELECT rowid, * FROM {quoted} ORDER BY rowid"):
        values = tuple(row)
        if table == "transports":
            replacement = replacements.get(
                (row["user_id"], row["transport_id"])
            )
            if replacement:
                values = tuple(replacement[key] for key in row.keys())
        digest.update(repr(values).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


class TransportRepairRepository:
    """Preserve the readonly source and verify a separately generated copy."""

    def __init__(self, source: Path) -> None:
        """Bind maintenance to one explicit source or mandatory backup."""
        self.source = source.resolve()

    def _validate(self, db: sqlite3.Connection) -> None:
        """Require canonical storage, sound ownership and known transports."""
        if (
            list(map(tuple, db.execute("SELECT version FROM game_schema")))
            != [(VERSION,)]
            or list(map(tuple, db.execute("PRAGMA integrity_check")))
            != [("ok",)]
            or db.execute("PRAGMA foreign_key_check").fetchone() is not None
        ):
            raise PersistenceError("Spielstandintegrität abweichend.")
        SqliteGameDatabase(self.source)._validate_structure(db)
        for row in db.execute("SELECT * FROM owned_vehicles"):
            load_vehicle_record(dict(row))

    def _inventory(
        self,
        db: sqlite3.Connection,
    ) -> tuple[dict[str, int], dict[tuple[str, str], dict[str, Any]]]:
        """Reject unknown defects before creating either output artifact."""
        self._validate(db)
        counts = {"transports": 0, "repaired_active": 0, "repaired_settled": 0}
        repairs = {}
        for record in db.execute(
            "SELECT rowid, * FROM transports ORDER BY rowid"
        ):
            row = dict(record)
            fixed = repaired_transport(row)
            counts["transports"] += 1
            if fixed != row:
                counts["repaired_" + row["status"]] += 1
                repairs[row["user_id"], row["transport_id"]] = fixed
        return counts, repairs

    def inspect(self) -> dict[str, int]:
        """Perform the execution checks without modifying source or outputs."""
        with closing(
            sqlite3.connect(
                self.source.as_uri() + "?mode=ro",
                uri=True,
            )
        ) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            return self._inventory(db)[0]

    def repair_to(self, target: Path, archive: Path) -> dict[str, int]:
        """Create and reconcile a new copy; roll back failed output."""
        target, archive = target.resolve(), archive.resolve()
        if len({self.source, target, archive}) != 3:
            raise ValueError("Source, target and archive must differ.")
        created: list[Path] = []
        try:
            with closing(
                sqlite3.connect(
                    self.source.as_uri() + "?mode=ro",
                    uri=True,
                )
            ) as source:
                source.row_factory = sqlite3.Row
                source.execute("PRAGMA query_only=ON")
                source.execute("BEGIN")
                counts, repairs = self._inventory(source)
                for path in (target, archive):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb"):
                        pass
                    created.append(path)
                with closing(sqlite3.connect(target)) as destination:
                    destination.row_factory = sqlite3.Row
                    source.backup(destination)
                    self._apply(source, destination, repairs, archive)
                    self._verify_archive(source, repairs, archive)
                    self._compare(source, destination, repairs)
            LOGGER.info(
                "Historical transport metadata repaired in a separate copy",
                extra={"event": "state.transport_repaired", "data": counts},
            )
            return counts
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            LOGGER.error(
                "Historical transport repair rolled back",
                extra={"event": "state.transport_repair_rolled_back"},
            )
            raise

    def _apply(
        self,
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        repairs: dict[tuple[str, str], dict[str, Any]],
        archive: Path,
    ) -> None:
        """Archive originals and insert canonical replacements atomically."""
        target.execute("PRAGMA foreign_keys=ON")
        with (
            archive.open("w", encoding="utf-8", newline="\n") as output,
            target,
        ):
            for (owner, trip), fixed in repairs.items():
                raw = source.execute(
                    "SELECT transport_snapshot FROM transports "
                    "WHERE user_id=? AND transport_id=?",
                    (owner, trip),
                ).fetchone()[0]
                output.write(
                    json.dumps(
                        {
                            "repair_version": 1,
                            "user_id": owner,
                            "transport_id": trip,
                            "original": raw,
                            "sha256": sha256(raw.encode()).hexdigest(),
                            "replacement_sha256": sha256(
                                fixed["transport_snapshot"].encode()
                            ).hexdigest(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                # The source and its immutable settled rows are never updated.
                # Guards remain enabled in the newly generated target as well.
                target.execute(
                    "DELETE FROM transports "
                    "WHERE user_id=? AND transport_id=?",
                    (owner, trip),
                )
                columns = ",".join(fixed)
                markers = ",".join("?" for _ in fixed)
                target.execute(
                    f"INSERT INTO transports ({columns}) VALUES ({markers})",
                    tuple(fixed.values()),
                )

    def _verify_archive(
        self,
        source: sqlite3.Connection,
        repairs: dict[tuple[str, str], dict[str, Any]],
        archive: Path,
    ) -> None:
        """Read back exact original documents and both recorded checksums."""
        records = [
            json.loads(line)
            for line in archive.read_text(encoding="utf-8").splitlines()
        ]
        if len(records) != len(repairs):
            raise PersistenceError("Reparaturarchiv unvollständig.")
        for item, ((owner, trip), fixed) in zip(records, repairs.items()):
            raw = source.execute(
                "SELECT transport_snapshot FROM transports "
                "WHERE user_id=? AND transport_id=?",
                (owner, trip),
            ).fetchone()[0]
            if item != {
                "repair_version": 1,
                "user_id": owner,
                "transport_id": trip,
                "original": raw,
                "sha256": sha256(raw.encode()).hexdigest(),
                "replacement_sha256": sha256(
                    fixed["transport_snapshot"].encode()
                ).hexdigest(),
            }:
                raise PersistenceError("Reparaturarchiv abweichend.")

    def _compare(
        self,
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        repairs: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        """Require exact equality except approved optional metadata."""
        schema = (
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
        )
        if list(map(tuple, source.execute(schema))) != list(
            map(tuple, target.execute(schema))
        ):
            raise PersistenceError("Reparaturschema abweichend.")
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ):
            if table_digest(source, row[0], repairs) != table_digest(
                target, row[0], {}
            ):
                raise PersistenceError("Reparaturabgleich fehlgeschlagen.")
        counts, remaining = self._inventory(target)
        if (
            remaining
            or counts["repaired_active"]
            or counts["repaired_settled"]
        ):
            raise PersistenceError("Reparatur unvollständig.")
