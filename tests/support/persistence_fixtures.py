"""Reusable relational persistence fixtures."""

import pytest

from app.composition.runtime import initialize_runtime_schema
from app.repositories.game_database import SqliteGameDatabase


@pytest.fixture
def relational(tmp_path):
    """Create an isolated two-player relational database."""
    database = SqliteGameDatabase(tmp_path / "fresh.db")
    database.initialize()
    initialize_runtime_schema(database)
    with database.connect() as connection:
        connection.executemany(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            [
                ("alice", "Alice", "test-only", 0),
                ("bob", "Bob", "test-only", 1),
            ],
        )
    return database
