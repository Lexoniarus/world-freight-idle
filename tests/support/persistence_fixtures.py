"""Reusable relational persistence fixtures."""

import pytest

from app.repositories.game_database import SqliteGameDatabase
from app.repositories.preferences import SqlitePreferenceStore
from app.repositories.relational_traffic import SqliteTrafficReader


@pytest.fixture
def relational(tmp_path):
    """Create an isolated two-player relational database."""
    database = SqliteGameDatabase(tmp_path / "fresh.db")
    database.initialize()
    SqlitePreferenceStore.initialize(database)
    SqliteTrafficReader.initialize(database)
    with database.connect() as connection:
        connection.executemany(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            [
                ("alice", "Alice", "test-only", 0),
                ("bob", "Bob", "test-only", 1),
            ],
        )
    return database
