"""Exact reconciliation of transformed market-stock databases."""

import json
import sqlite3
from dataclasses import dataclass

from app.domain.errors import PersistenceError
from app.repositories.game_schema import VERSION
from app.repositories.transport_repair import table_digest


@dataclass(frozen=True, slots=True)
class MarketStockUpgradeReconciler:
    """Prove that only approved market-stock facts changed."""

    now: float

    def validate(
        self,
        source: sqlite3.Connection,
        target: sqlite3.Connection,
    ) -> None:
        """Reconcile all tables and historical JSON before activation."""
        self._validate_schema_version(source, target)
        self._validate_preserved_tables(source, target)
        self._validate_offer_rows(target, self.expected_offer_rows(source))
        self._validate_route_references(
            target,
            self.expected_route_references(source),
        )
        self._validate_database_integrity(target)

    @staticmethod
    def _validate_schema_version(
        source: sqlite3.Connection,
        target: sqlite3.Connection,
    ) -> None:
        """Require unchanged schema except for the upgraded offer table."""
        schema_query = (
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT IN ('contract_offers','offers_scope') "
            "ORDER BY name"
        )
        if list(map(tuple, source.execute(schema_query))) != list(
            map(tuple, target.execute(schema_query))
        ) or list(
            map(tuple, target.execute("SELECT version FROM game_schema"))
        ) != [(VERSION,)]:
            raise PersistenceError("Übernahmeschema abweichend.")

    @staticmethod
    def _validate_preserved_tables(
        source: sqlite3.Connection,
        target: sqlite3.Connection,
    ) -> None:
        """Require all unrelated table bytes to remain identical."""
        for (table,) in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ):
            if table in {
                "contract_offers",
                "offer_route_references",
                "game_schema",
            }:
                continue
            if table_digest(source, table, {}) != table_digest(
                target, table, {}
            ):
                raise PersistenceError(
                    "Übernahmeabgleich fehlgeschlagen: " + table
                )

    def expected_offer_rows(
        self,
        source: sqlite3.Connection,
    ) -> tuple[tuple[object, ...], ...]:
        """Project exact live offer rows expected after conversion."""
        expected: list[tuple[object, ...]] = []
        for row in source.execute(
            "SELECT rowid,* FROM contract_offers ORDER BY rowid"
        ):
            if row["expires_at"] > self.now:
                values = dict(row)
                raw = json.loads(values["offer_snapshot"])
                raw["data"]["expires_at"] = None
                values["expires_at"] = None
                values["offer_snapshot"] = json.dumps(raw, allow_nan=False)
                expected.append(tuple(values.values()))
        return tuple(expected)

    @staticmethod
    def _validate_offer_rows(
        target: sqlite3.Connection,
        expected: tuple[tuple[object, ...], ...],
    ) -> None:
        """Require the target offer table to match the live projection."""
        actual = tuple(
            map(
                tuple,
                target.execute(
                    "SELECT rowid,* FROM contract_offers ORDER BY rowid"
                ),
            )
        )
        if expected != actual:
            raise PersistenceError("Auftragsabgleich fehlgeschlagen.")

    def expected_route_references(
        self,
        source: sqlite3.Connection,
    ) -> tuple[tuple[object, ...], ...] | None:
        """Project bindings retained for live offers, when supported."""
        if not source.execute(
            "SELECT 1 FROM sqlite_master WHERE name='offer_route_references'"
        ).fetchone():
            return None
        return tuple(
            map(
                tuple,
                source.execute(
                    "SELECT r.rowid,r.* FROM offer_route_references r "
                    "JOIN contract_offers o ON o.user_id=r.user_id AND "
                    "o.contract_id=r.contract_id WHERE o.expires_at>? "
                    "ORDER BY r.rowid",
                    (self.now,),
                ),
            )
        )

    @staticmethod
    def _validate_route_references(
        target: sqlite3.Connection,
        expected: tuple[tuple[object, ...], ...] | None,
    ) -> None:
        """Require retained route bindings to match their source rows."""
        if expected is None:
            return
        actual = tuple(
            map(
                tuple,
                target.execute(
                    "SELECT rowid,* FROM offer_route_references ORDER BY rowid"
                ),
            )
        )
        if expected != actual:
            raise PersistenceError("Routenbindungsabgleich fehlgeschlagen.")

    @staticmethod
    def _validate_database_integrity(target: sqlite3.Connection) -> None:
        """Require final foreign keys and SQLite integrity checks."""
        if target.execute("PRAGMA foreign_key_check").fetchone() or list(
            map(tuple, target.execute("PRAGMA integrity_check"))
        ) != [("ok",)]:
            raise PersistenceError("Zieldatenbank inkonsistent.")
