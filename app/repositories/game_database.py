"""SQLite resource ownership and explicit relational schema validation."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from app.domain.errors import PersistenceError, UnsupportedGameSchema
from app.repositories.game_schema import REQUIRED_TABLES, SCHEMA, VERSION

LOGGER = logging.getLogger(__name__)


class SqliteGameDatabase:
    """Own connections and never upgrade existing player files implicitly."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._active: ContextVar[sqlite3.Connection | None] = ContextVar(
            "game_transaction", default=None
        )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Reuse the transaction connection or reliably close a fresh one."""
        connection = self._active.get()
        owned = connection is None
        try:
            if connection is None:
                connection = sqlite3.connect(
                    self.path, timeout=15, isolation_level=None
                )
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        except sqlite3.Error as exc:
            LOGGER.error(
                "Game persistence operation failed",
                extra={"event": "state.persistence_error"},
            )
            raise PersistenceError("Spielstand nicht verfügbar.") from exc
        finally:
            if owned and connection is not None:
                connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Serialize mutations and roll back the complete outer use case."""
        if self._active.get() is not None:
            yield
            return
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            token = self._active.set(connection)
            try:
                yield
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                self._active.reset(token)

    def initialize(self) -> None:
        """Create a fresh schema or require the exact supported revision."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not tables:
                connection.executescript("BEGIN IMMEDIATE;" + SCHEMA)
                connection.commit()
            elif not REQUIRED_TABLES.issubset(tables) or "kv" in tables:
                raise UnsupportedGameSchema(
                    "Spielstandschema benötigt einen expliziten Import."
                )
            versions = connection.execute(
                "SELECT version FROM game_schema"
            ).fetchall()
            if [row[0] for row in versions] != [VERSION]:
                raise UnsupportedGameSchema("Unbekannte Spielstandversion.")
            self._validate_structure(connection)
        LOGGER.info(
            "Game schema validated",
            extra={
                "event": "state.schema_validated",
                "data": {
                    "schema_version": VERSION,
                },
            },
        )

    def _validate_structure(self, connection: sqlite3.Connection) -> None:
        """Reject incomplete tables and missing concurrency safeguards."""
        expected = {
            "player_states": {"user_id", "cash", "completed", "reputation"},
            "owned_vehicles": {
                "user_id",
                "vehicle_id",
                "name",
                "mode",
                "model_id",
                "capacity_tons",
                "status",
                "operating_cost_eur_per_km",
                "facility_uid",
                "location_snapshot",
            },
            "contract_offers": {
                "user_id",
                "contract_id",
                "created_at",
                "expires_at",
                "market_model",
                "offer_snapshot",
                "origin_facility_uid",
                "destination_facility_uid",
            },
            "transports": {
                "user_id",
                "transport_id",
                "vehicle_id",
                "contract_id",
                "origin_facility_uid",
                "destination_facility_uid",
                "status",
                "departed_at",
                "arrives_at",
                "settled_at",
                "operating_cost_eur",
                "payout_eur",
                "transport_snapshot",
            },
        }
        for table, columns in expected.items():
            found = {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table})")
            }
            if found != columns:
                raise UnsupportedGameSchema("Spielstandtabellen abweichend.")
        objects = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('index','trigger')"
            )
        }
        if (
            not {"one_active_transport_per_vehicle", "retain_settlement"}
            <= objects
        ):
            raise UnsupportedGameSchema("Spielstandschutz unvollständig.")
