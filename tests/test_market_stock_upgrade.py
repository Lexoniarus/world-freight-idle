"""Explicit market schema adoption preserves accounts and every transport."""

import json
import sqlite3
from contextlib import closing
from hashlib import sha256
from unittest.mock import patch

import pytest

from app.bootstrap import build_market_stock_upgrade
from app.domain.errors import PersistenceError, UnsupportedGameSchema
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_schema import VERSION
from app.repositories.market_stock_upgrade import MarketStockUpgradeRepository
from app.repositories.previous_game_schema import SCHEMA as PREVIOUS_SCHEMA
from tests.transport_fixtures import add_transport


@pytest.fixture
def old_market_source(game, database, tmp_path):
    add_transport(game)
    path = tmp_path / "old-market.db"
    now = game.now()
    with (
        closing(sqlite3.connect(path)) as target,
        database.connect() as source,
    ):
        target.executescript(PREVIOUS_SCHEMA)
        for table in (
            "users",
            "player_states",
            "owned_vehicles",
            "contract_offers",
            "transports",
        ):
            for index, row in enumerate(
                source.execute(f"SELECT * FROM {table}")
            ):
                values = dict(row)
                if table == "contract_offers":
                    values["expires_at"] = now + 3600
                    if index == 0:
                        values["created_at"] = 0
                        values["expires_at"] = 1
                    raw = json.loads(values["offer_snapshot"])
                    raw["data"]["created_at"] = values["created_at"]
                    raw["data"]["expires_at"] = values["expires_at"]
                    values["offer_snapshot"] = json.dumps(raw)
                target.execute(
                    f"INSERT INTO {table} VALUES ({','.join('?' for _ in values)})",
                    tuple(values.values()),
                )
        target.execute(
            "CREATE TABLE offer_route_references (user_id TEXT, contract_id TEXT, relation_id TEXT, revision TEXT)"
        )
        target.execute(
            "INSERT INTO offer_route_references SELECT user_id,contract_id,'route','revision' FROM contract_offers"
        )
        target.execute("CREATE TABLE annotations (value TEXT)")
        target.execute("INSERT INTO annotations VALUES ('preserve verbatim')")
        target.commit()
    return path, now


def test_market_upgrade_preserves_source_history_and_only_converts_live_offers(
    old_market_source, tmp_path
):
    source, now = old_market_source
    before = sha256(source.read_bytes()).hexdigest()
    upgrade = build_market_stock_upgrade(source, now)
    counts = upgrade.inspect()
    assert counts["expired_offers"] == 1
    assert counts["transports"] == 1
    target = tmp_path / "upgraded.db"
    assert upgrade.upgrade_to(target) == counts
    assert sha256(source.read_bytes()).hexdigest() == before
    with pytest.raises(UnsupportedGameSchema):
        SqliteGameDatabase(source).initialize()
    with (
        closing(sqlite3.connect(source)) as original,
        closing(sqlite3.connect(target)) as output,
    ):
        assert output.execute(
            "SELECT version FROM game_schema"
        ).fetchone() == (VERSION,)
        assert (
            output.execute(
                "SELECT count(*) FROM contract_offers WHERE expires_at IS NULL"
            ).fetchone()[0]
            == counts["retained_offers"]
        )
        assert (
            output.execute(
                "SELECT transport_snapshot FROM transports"
            ).fetchall()
            == original.execute(
                "SELECT transport_snapshot FROM transports"
            ).fetchall()
        )
        assert output.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert output.execute("PRAGMA foreign_key_check").fetchall() == []
        for (raw,) in output.execute(
            "SELECT offer_snapshot FROM contract_offers"
        ):
            assert json.loads(raw)["data"]["expires_at"] is None
    with pytest.raises(FileExistsError):
        upgrade.upgrade_to(target)
    assert target.exists()


def test_market_upgrade_rejects_unknown_schema_and_rolls_back_bad_output(
    old_market_source, tmp_path
):
    source, now = old_market_source
    upgrade = MarketStockUpgradeRepository(source, now)
    target = tmp_path / "failed.db"
    with patch.object(
        upgrade, "_compare", side_effect=PersistenceError("mismatch")
    ):
        with pytest.raises(PersistenceError, match="mismatch"):
            upgrade.upgrade_to(target)
    assert not target.exists()
    with closing(sqlite3.connect(source)) as db:
        db.execute("DROP TRIGGER retain_settlement")
        db.commit()
    with pytest.raises(PersistenceError, match="Quellschema"):
        upgrade.inspect()
    with closing(sqlite3.connect(source)) as db:
        db.execute("UPDATE game_schema SET version='unknown'")
        db.commit()
    with pytest.raises(PersistenceError, match="Unbekannter"):
        upgrade.upgrade_to(target)
    assert not target.exists()


def test_market_upgrade_reconciliation_detects_unapproved_changes(
    old_market_source, tmp_path
):
    source, now = old_market_source
    upgrade = MarketStockUpgradeRepository(source, now)
    target = tmp_path / "target.db"
    with (
        closing(sqlite3.connect(source)) as original,
        closing(sqlite3.connect(target)) as output,
    ):
        original.row_factory = output.row_factory = sqlite3.Row
        original.backup(output)
        upgrade._apply(output)
        upgrade._compare(original, output)
        for sql, expected in (
            ("DELETE FROM annotations", "Übernahmeabgleich"),
            ("DELETE FROM contract_offers", "Auftragsabgleich"),
            ("DELETE FROM offer_route_references", "Routenbindungsabgleich"),
            ("UPDATE game_schema SET version='other'", "Übernahmeschema"),
            ("CREATE TABLE unexpected (id INTEGER)", "Übernahmeschema"),
        ):
            output.execute("BEGIN")
            output.execute(sql)
            with pytest.raises(PersistenceError, match=expected):
                upgrade._compare(original, output)
            output.rollback()


def test_market_upgrade_rejects_stock_collision_and_failed_integrity(
    old_market_source, tmp_path
):
    source, now = old_market_source
    upgrade = MarketStockUpgradeRepository(source, now)

    class UnhealthyOutput(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql == "PRAGMA integrity_check":
                return super().execute("SELECT 'simulated storage corruption'")
            return super().execute(sql, parameters)

    with (
        closing(sqlite3.connect(source)) as original,
        closing(
            sqlite3.connect(":memory:", factory=UnhealthyOutput)
        ) as output,
    ):
        original.row_factory = output.row_factory = sqlite3.Row
        original.backup(output)
        upgrade._apply(output)
        with pytest.raises(PersistenceError, match="inkonsistent"):
            upgrade._compare(original, output)
        original.execute("CREATE TABLE market_templates (unexpected TEXT)")
        original.commit()
    with pytest.raises(PersistenceError, match="Vorratstabellen"):
        upgrade.upgrade_to(tmp_path / "rejected.db")
    assert not (tmp_path / "rejected.db").exists()


def test_market_upgrade_cli_requires_backup_and_preserves_source(
    old_market_source, tmp_path, capsys
):
    from scripts.upgrade_market_stock import main

    source, now = old_market_source
    before = sha256(source.read_bytes()).hexdigest()
    backup, output = tmp_path / "backup.db", tmp_path / "output.db"
    base = ["upgrade_market_stock.py", "--source", str(source)]
    with (
        patch("sys.argv", [*base, "--check"]),
        patch("time.time", return_value=now),
    ):
        main()
    assert json.loads(capsys.readouterr().out)["expired_offers"] == 1
    for args in (
        [],
        ["--check", "--backup", str(backup)],
        ["--backup", str(source), "--output", str(output)],
    ):
        with patch("sys.argv", [*base, *args]), pytest.raises(SystemExit):
            main()
    args = [*base, "--backup", str(backup), "--output", str(output)]
    with patch("sys.argv", args), patch("time.time", return_value=now):
        main()
    assert backup.exists() and output.exists()
    assert sha256(source.read_bytes()).hexdigest() == before
    with patch("sys.argv", args), pytest.raises(SystemExit):
        main()
