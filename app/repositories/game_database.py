"""SQLite resource ownership and explicit relational schema validation."""

import logging
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
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
            try:
                self._validate_structure(connection)
            except UnsupportedGameSchema:
                LOGGER.error(
                    "Game schema safeguards rejected",
                    extra={"event": "state.schema_rejected"},
                )
                raise
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
        with closing(sqlite3.connect(":memory:")) as reference:
            reference.executescript(SCHEMA)
            self._validate_keys(connection, reference)
            self._validate_guards(connection, reference)

    def _validate_keys(
        self, connection: sqlite3.Connection, reference: sqlite3.Connection
    ) -> None:
        """Require the supported owner identities and foreign-key links."""
        for table in sorted(REQUIRED_TABLES):
            expected_keys = [
                (row[1], row[5])
                for row in reference.execute(f"PRAGMA table_info({table})")
                if row[5]
            ]
            actual_keys = [
                (row[1], row[5])
                for row in connection.execute(f"PRAGMA table_info({table})")
                if row[5]
            ]
            expected_links = list(
                reference.execute(f"PRAGMA foreign_key_list({table})")
            )
            actual_links = [
                tuple(row)
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                )
            ]
            if actual_keys != expected_keys or actual_links != expected_links:
                raise UnsupportedGameSchema(
                    "Spielstandschluessel abweichend: " + table
                )

    def _validate_guards(
        self, connection: sqlite3.Connection, reference: sqlite3.Connection
    ) -> None:
        """Check executable guards, including their table and predicates."""
        for name in ("one_active_transport_per_vehicle", "retain_settlement"):
            expected = reference.execute(
                "SELECT type, tbl_name, sql FROM sqlite_master WHERE name=?",
                (name,),
            ).fetchone()
            actual = connection.execute(
                "SELECT type, tbl_name, sql FROM sqlite_master WHERE name=?",
                (name,),
            ).fetchone()
            if (
                actual is None
                or tuple(actual[:2]) != tuple(expected[:2])
                or schema_sql_tokens(actual[2])
                != schema_sql_tokens(expected[2])
            ):
                raise UnsupportedGameSchema(
                    "Spielstandschutz abweichend: " + name
                )


def schema_sql_tokens(sql: str) -> tuple[str, ...]:
    """Compare owned schema SQL without changing quoted literal contents."""
    tokens = re.findall(
        r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`|\[[^\]]*\]"
        r"|--[^\n]*|/\*.*?\*/|\w+|[^\s]",
        sql,
        re.DOTALL,
    )
    return tuple(
        token if token[0] in "'\"`[" else token.lower()
        for token in tokens
        if not token.startswith(("--", "/*"))
    )
