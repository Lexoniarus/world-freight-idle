"""Atomic legacy-state reconciliation and rollback."""

from unittest.mock import patch

import pytest

from app.domain.errors import PersistenceError
from app.repositories.game_database import SqliteGameDatabase


def test_import_rolls_back_reconciliation_and_write_failures(
    legacy_source, tmp_path
):
    path, importer, _, now, _ = legacy_source
    original = path.read_bytes()
    target = tmp_path / "failed.db"
    for hook in (
        "app.repositories.legacy_game_import.reconcile_import",
        "app.repositories.game_state.SqliteGameStateRepository.save_transport",
    ):
        with patch(hook, side_effect=PersistenceError("simulated")):
            with pytest.raises(PersistenceError):
                importer.import_to(target, now)
        assert not target.exists()
        assert path.read_bytes() == original


def test_import_reconciliation_detects_retained_value_changes(
    legacy_source, tmp_path
):
    from app.repositories.legacy_game_import import reconcile_import

    _, importer, _, now, _ = legacy_source
    target = tmp_path / "reconcile.db"
    importer.import_to(target, now)
    database = SqliteGameDatabase(target)
    profiles = importer._read_profiles(now)
    reconcile_import(database, profiles)
    for statement in (
        "UPDATE users SET created_at=101 WHERE id='a'",
        "UPDATE player_states SET cash=cash+1 WHERE user_id='a'",
        "UPDATE owned_vehicles SET name='changed' WHERE user_id='a'",
    ):
        with pytest.raises(PersistenceError):
            with database.transaction():
                with database.connect() as connection:
                    connection.execute(statement)
                reconcile_import(database, profiles)
        reconcile_import(database, profiles)

    with database.connect() as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "CREATE TABLE corrupt_link(owner TEXT REFERENCES users(id))"
        )
        connection.execute("INSERT INTO corrupt_link VALUES('unknown')")
    with pytest.raises(PersistenceError, match="integrity check failed"):
        reconcile_import(database, profiles)
