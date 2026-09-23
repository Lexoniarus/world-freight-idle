"""Reject same-name but ineffective schema guards without modifying files."""

import sqlite3
from contextlib import closing

import pytest

from app.domain.errors import UnsupportedGameSchema
from app.repositories.game_database import (
    SqliteGameDatabase,
    schema_sql_tokens,
)
from app.repositories.game_schema import SCHEMA


@pytest.mark.parametrize(
    "definition",
    [
        "CREATE INDEX one_active_transport_per_vehicle ON transports(user_id, vehicle_id) WHERE status='active'",
        "CREATE UNIQUE INDEX one_active_transport_per_vehicle ON transports(vehicle_id, user_id) WHERE status='active'",
        "CREATE UNIQUE INDEX one_active_transport_per_vehicle ON transports(user_id, vehicle_id) WHERE status='settled'",
        "CREATE UNIQUE INDEX one_active_transport_per_vehicle ON transports(user_id, vehicle_id)",
        "CREATE UNIQUE INDEX one_active_transport_per_vehicle ON owned_vehicles(user_id, vehicle_id)",
        "CREATE TRIGGER one_active_transport_per_vehicle BEFORE UPDATE ON transports BEGIN SELECT 1; END",
    ],
)
def test_schema_rejects_ineffective_unique_index(tmp_path, definition, caplog):
    database = SqliteGameDatabase(tmp_path / "guard.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute("DROP INDEX one_active_transport_per_vehicle")
        connection.execute(definition)
    before = database.path.read_bytes()
    with pytest.raises(UnsupportedGameSchema, match="one_active"):
        database.initialize()
    assert database.path.read_bytes() == before
    assert any(
        getattr(r, "event", None) == "state.schema_rejected"
        for r in caplog.records
    )


@pytest.mark.parametrize(
    "definition",
    [
        "CREATE TRIGGER retain_settlement BEFORE UPDATE ON transports WHEN OLD.status='settled' BEGIN SELECT 1; END",
        "CREATE TRIGGER retain_settlement BEFORE UPDATE ON transports WHEN OLD.status='active' BEGIN SELECT RAISE(ABORT, 'Settled transport is immutable'); END",
        "CREATE TRIGGER retain_settlement AFTER UPDATE ON transports WHEN OLD.status='settled' BEGIN SELECT RAISE(ABORT, 'Settled transport is immutable'); END",
        "CREATE TRIGGER retain_settlement BEFORE UPDATE ON transports WHEN OLD.status='settled' BEGIN SELECT RAISE(IGNORE); END",
        "CREATE TRIGGER retain_settlement BEFORE UPDATE ON owned_vehicles WHEN OLD.status='settled' BEGIN SELECT RAISE(ABORT, 'Settled transport is immutable'); END",
    ],
)
def test_schema_rejects_ineffective_settlement_trigger(tmp_path, definition):
    database = SqliteGameDatabase(tmp_path / "guard.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute("DROP TRIGGER retain_settlement")
        connection.execute(definition)
    before = database.path.read_bytes()
    with pytest.raises(UnsupportedGameSchema, match="retain_settlement"):
        database.initialize()
    assert database.path.read_bytes() == before


@pytest.mark.parametrize(
    "original,replacement",
    [
        (
            "PRIMARY KEY(user_id, transport_id)",
            "UNIQUE(user_id, transport_id)",
        ),
        (
            "PRIMARY KEY (user_id, vehicle_id)",
            "PRIMARY KEY (vehicle_id, user_id)",
        ),
        (
            "user_id TEXT PRIMARY KEY REFERENCES users(id)",
            "user_id TEXT PRIMARY KEY",
        ),
        (
            "REFERENCES owned_vehicles(user_id, vehicle_id)",
            "REFERENCES owned_vehicles(vehicle_id, user_id)",
        ),
    ],
)
def test_schema_rejects_missing_or_changed_ownership_keys(
    tmp_path, original, replacement
):
    path = tmp_path / "keys.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(SCHEMA.replace(original, replacement))
    before = path.read_bytes()
    with pytest.raises(UnsupportedGameSchema, match="schluessel"):
        SqliteGameDatabase(path).initialize()
    assert path.read_bytes() == before


def test_schema_accepts_formatting_but_preserves_literals(tmp_path):
    database = SqliteGameDatabase(tmp_path / "formatted.db")
    with closing(sqlite3.connect(database.path)) as connection:
        connection.executescript(
            SCHEMA.replace(
                "ON transports(user_id, vehicle_id) WHERE status = 'active'",
                "on transports ( user_id , vehicle_id )\nwhere status='active'",
            ).replace("BEGIN SELECT RAISE", "begin /* guard */ select raise")
        )
    database.initialize()
    database.initialize()
    assert schema_sql_tokens(
        "SELECT 'a  b', 'It''s', \"Name\" -- comment\n"
    ) == ("select", "'a  b'", ",", "'It''s'", ",", '"Name"')
    assert schema_sql_tokens("'a b'") != schema_sql_tokens("'a  b'")
    assert schema_sql_tokens("'active'") != schema_sql_tokens("'ACTIVE'")
