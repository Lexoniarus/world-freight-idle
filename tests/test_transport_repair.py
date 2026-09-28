"""Offline repair preserves source, money, history and original documents."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, replace
from hashlib import sha256
from unittest.mock import patch

import pytest

from app.bootstrap import build_transport_repair
from app.domain.errors import PersistenceError
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.transport_repair import repaired_transport, table_digest
from tests.test_market_preparation import require_value
from tests.test_runtime_views import active_trip as active_trip


def damage_approach(database, trip, *, settled=False):
    with database.connect() as db:
        row = dict(db.execute("SELECT rowid,* FROM transports").fetchone())
        data = json.loads(row["transport_snapshot"])
        data["data"]["dispatch_route"] = {
            "start": asdict(replace(trip.origin, facility_uid="old-start")),
            "pickup": asdict(trip.origin),
            "destination": asdict(trip.destination),
            "delivery": asdict(trip.route),
            "approach": None,
        }
        if settled:
            data["data"].update(status="settled", settled_at=trip.arrives_at)
        raw = json.dumps(data)
        db.execute(
            "UPDATE transports SET transport_snapshot=?,status=?,settled_at=?",
            (
                raw,
                "settled" if settled else "active",
                trip.arrives_at if settled else None,
            ),
        )
    return raw


@pytest.mark.parametrize("settled", [False, True])
def test_repair_preserves_all_values_and_archives_original(
    active_trip, database, tmp_path, settled
):
    raw = damage_approach(database, active_trip, settled=settled)
    tool = build_transport_repair(database.path)
    counts = tool.inspect()
    assert counts["repaired_settled" if settled else "repaired_active"] == 1
    output, archive = tmp_path / "repaired.db", tmp_path / "archive.jsonl"
    assert tool.repair_to(output, archive) == counts
    archived = json.loads(archive.read_text(encoding="utf-8"))
    assert archived["original"] == raw
    assert archived["sha256"] == sha256(raw.encode()).hexdigest()
    assert tool.inspect() == counts
    destination = SqliteGameDatabase(output)
    destination.initialize()
    repository = SqliteGameUnitOfWork(destination, "test-owner").repository
    fixed = repository.list_transports()[0]
    assert fixed.dispatch_route is None
    assert fixed.route == active_trip.route
    assert fixed.journey == active_trip.journey
    assert fixed.payout_eur == active_trip.payout_eur
    assert fixed.status == ("settled" if settled else "active")
    assert require_value(repository.get_player()).cash == 175000
    with destination.connect() as db:
        assert "retain_settlement" in {
            r[0] for r in db.execute("SELECT name FROM sqlite_master")
        }
        assert table_digest(db, "transports", {})
    assert build_transport_repair(output).inspect()["repaired_active"] == 0
    with pytest.raises(FileExistsError):
        tool.repair_to(output, tmp_path / "other.jsonl")
    assert output.exists() and not (tmp_path / "other.jsonl").exists()
    with pytest.raises(ValueError):
        tool.repair_to(database.path, archive)


def test_repair_rejects_unknown_damage_and_removes_failed_outputs(
    active_trip, database, tmp_path
):
    damage_approach(database, active_trip)
    tool = build_transport_repair(database.path)
    with database.connect() as db:
        row = dict(db.execute("SELECT rowid,* FROM transports").fetchone())
    for change in (
        "missing",
        "unknown",
        "wrong-route",
        "wrong-city",
        "malformed",
    ):
        document = json.loads(row["transport_snapshot"])
        plan = document["data"]["dispatch_route"]
        if change == "missing":
            document["data"]["dispatch_route"] = {}
        elif change == "unknown":
            plan["unknown"] = True
        elif change == "wrong-route":
            plan["delivery"]["distance_km"] += 1
        elif change == "wrong-city":
            plan["start"]["city"]["city_uid"] = "elsewhere"
        else:
            plan["start"] = None
        with pytest.raises((PersistenceError, ValueError)):
            repaired_transport(
                {**row, "transport_snapshot": json.dumps(document)}
            )
    output, archive = tmp_path / "out.db", tmp_path / "archive.jsonl"
    for method in ("_apply", "_compare"):
        with patch.object(
            tool, method, side_effect=PersistenceError("injected")
        ):
            with pytest.raises(PersistenceError):
                tool.repair_to(output, archive)
        assert not output.exists() and not archive.exists()
    archive.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        tool.repair_to(output, archive)
    assert not output.exists() and archive.read_text() == "existing"
    with database.connect() as db:
        db.execute("UPDATE game_schema SET version='unsupported'")
    with pytest.raises(PersistenceError):
        tool.inspect()


def test_repair_reconciliation_and_archive_reject_any_unapproved_change(
    active_trip,
    database,
    tmp_path,
    game,
):
    damage_approach(database, active_trip)
    tool = build_transport_repair(database.path)
    target, archive = tmp_path / "out.db", tmp_path / "original.jsonl"
    before = database.path.read_bytes()
    tool.repair_to(target, archive)
    assert database.path.read_bytes() == before
    with (
        database.connect() as source,
        closing(sqlite3.connect(target)) as destination,
    ):
        destination.row_factory = sqlite3.Row
        _, repairs = tool._inventory(source)
        tool._compare(source, destination, repairs)
        destination.execute("CREATE TABLE unexpected (value TEXT)")
        with pytest.raises(PersistenceError, match="schema"):
            tool._compare(source, destination, repairs)
        destination.execute("DROP TABLE unexpected")
        destination.execute("UPDATE users SET password_hash='changed'")
        with pytest.raises(PersistenceError, match="abgleich"):
            tool._compare(source, destination, repairs)
        destination.rollback()
        with patch.object(
            tool, "_inventory", return_value=({"repaired_active": 1}, repairs)
        ):
            with pytest.raises(PersistenceError):
                tool._compare(source, destination, repairs)
        original = archive.read_text(encoding="utf-8")
        archive.write_text("", encoding="utf-8")
        with pytest.raises(PersistenceError):
            tool._verify_archive(source, repairs, archive)
        archive.write_text(
            original.replace('"repair_version": 1', '"repair_version": 2'),
            encoding="utf-8",
        )
        with pytest.raises(PersistenceError):
            tool._verify_archive(source, repairs, archive)
    # Normal game settlement, never the repair tool, applies the due payout.
    unit = SqliteGameUnitOfWork(SqliteGameDatabase(target), "test-owner")
    game.unit_of_work = unit
    game.state_repository = unit.repository
    game.market_lifecycle.unit_of_work = unit
    game.now = lambda: active_trip.arrives_at + 1
    assert game.reconcile_arrival()
    paid = unit.repository.get_player()
    assert require_value(paid).cash == 175000 + active_trip.payout_eur
    assert not game.reconcile_arrival()
    assert unit.repository.get_player() == paid
    assert database.path.read_bytes() == before
