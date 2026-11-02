"""Narrow schema transformation for legacy market stock."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass

from app.repositories.game_schema import SCHEMA, VERSION


@dataclass(frozen=True, slots=True)
class MarketStockUpgradeTransformer:
    """Replace only live offer expiry semantics and route references."""

    now: float

    def apply(self, database: sqlite3.Connection) -> None:
        """Rebuild only the offer table, preserving live IDs and row order."""
        database.execute("PRAGMA foreign_keys=OFF")
        with database:
            self._create_replacement_offer_table(database)
            self._copy_live_offers(database)
            self._replace_offer_table(database)
            self._remove_orphan_route_references(database)
            database.execute("UPDATE game_schema SET version=?", (VERSION,))
        database.execute("PRAGMA foreign_keys=ON")

    @staticmethod
    def _create_replacement_offer_table(
        database: sqlite3.Connection,
    ) -> None:
        """Create the current offer table under a temporary name."""
        with closing(sqlite3.connect(":memory:")) as reference:
            reference.executescript(SCHEMA)
            create = reference.execute(
                "SELECT sql FROM sqlite_master WHERE name='contract_offers'"
            ).fetchone()[0]
        database.execute(
            create.replace("contract_offers", "stock_upgrade_offers", 1)
        )

    def _copy_live_offers(self, database: sqlite3.Connection) -> None:
        """Copy live offers while removing their obsolete expiry."""
        rows = list(
            database.execute(
                "SELECT rowid,* FROM contract_offers ORDER BY rowid"
            )
        )
        for row in rows:
            if row["expires_at"] <= self.now:
                continue
            raw = json.loads(row["offer_snapshot"])
            raw["data"]["expires_at"] = None
            values = dict(row)
            values["expires_at"] = None
            values["offer_snapshot"] = json.dumps(raw, allow_nan=False)
            database.execute(
                "INSERT INTO stock_upgrade_offers("
                "rowid,user_id,contract_id,"
                "origin_facility_uid,destination_facility_uid,created_at,"
                "expires_at,market_model,offer_snapshot) VALUES "
                "(?,?,?,?,?,?,?,?,?)",
                tuple(values.values()),
            )

    @staticmethod
    def _replace_offer_table(database: sqlite3.Connection) -> None:
        """Activate the replacement table and its scope index."""
        database.execute("DROP TABLE contract_offers")
        database.execute(
            "ALTER TABLE stock_upgrade_offers RENAME TO contract_offers"
        )
        database.execute(
            "CREATE INDEX offers_scope ON contract_offers "
            "(user_id, origin_facility_uid, expires_at)"
        )

    @staticmethod
    def _remove_orphan_route_references(
        database: sqlite3.Connection,
    ) -> None:
        """Remove route bindings whose expired offer was not retained."""
        if not database.execute(
            "SELECT 1 FROM sqlite_master WHERE name='offer_route_references'"
        ).fetchone():
            return
        database.execute(
            "DELETE FROM offer_route_references WHERE NOT EXISTS "
            "(SELECT 1 FROM contract_offers o WHERE "
            "o.user_id=offer_route_references.user_id AND "
            "o.contract_id=offer_route_references.contract_id)"
        )
