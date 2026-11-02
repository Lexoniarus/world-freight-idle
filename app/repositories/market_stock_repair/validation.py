"""Shared validation and stable row reads for offline market repair."""

import sqlite3
from pathlib import Path

from app.domain.errors import PersistenceError
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_schema import VERSION


class MarketStockRepairDatabaseValidator:
    """Validate one immutable game database before maintenance reads."""

    def __init__(self, source: Path) -> None:
        """Bind structural validation to one explicit source path."""
        self.source = source.resolve()

    def validate(self, database: sqlite3.Connection) -> None:
        """Require the current sound schema and complete stock tables."""
        required = {
            "market_templates",
            "market_offer_templates",
            "market_template_uses",
            "market_stock_cursors",
            "market_stock_pending",
            "market_preparations",
            "market_coverage",
        }
        present = {
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        version = list(
            map(
                tuple,
                database.execute("SELECT version FROM game_schema"),
            )
        )
        integrity = list(
            map(tuple, database.execute("PRAGMA integrity_check"))
        )
        if (
            not required <= present
            or version != [(VERSION,)]
            or integrity != [("ok",)]
            or database.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise PersistenceError("Spielstandintegrität abweichend.")
        SqliteGameDatabase(self.source)._validate_structure(database)


def read_table_rows(
    database: sqlite3.Connection,
    table: str,
) -> tuple[tuple[object, ...], ...]:
    """Read stable full-table values for copy reconciliation."""
    return tuple(
        map(
            tuple,
            database.execute(f'SELECT * FROM "{table}" ORDER BY rowid'),
        )
    )


def read_selected_rows(
    database: sqlite3.Connection,
    table: str,
    where: str,
    parameters: tuple[str, ...],
) -> list[dict[str, object]]:
    """Read explicit rows for the private rollback archive."""
    return [
        dict(row)
        for row in database.execute(
            f'SELECT * FROM "{table}" WHERE {where} ORDER BY rowid',
            parameters,
        )
    ]
