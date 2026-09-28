"""Explicit offline 1.1.0 to 1.2.0 upgrade with complete reconciliation."""

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from app.domain.errors import PersistenceError
from app.repositories.game_database import (
    SqliteGameDatabase,
    schema_sql_tokens,
)
from app.repositories.game_schema import SCHEMA, VERSION
from app.repositories.game_state import (
    load_offer_record,
    load_transport_record,
)
from app.repositories.market_stock import SqliteMarketStockStore
from app.repositories.previous_game_schema import SCHEMA as PREVIOUS_SCHEMA
from app.repositories.transport_repair import table_digest

LOGGER = logging.getLogger(__name__)


class MarketStockUpgradeRepository:
    """Copy supported storage and change only open offer expiry semantics."""

    def __init__(self, source: Path, now: float) -> None:
        """Bind an explicit source and one consistent upgrade cutoff."""
        self.source = source.resolve()
        self.now = now

    def inspect(self) -> dict[str, int]:
        """Validate without opening the source for writing."""
        with closing(
            sqlite3.connect(
                self.source.as_uri() + "?mode=ro",
                uri=True,
            )
        ) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            self._validate(db)
            return self._counts(db)

    def upgrade_to(self, target: Path) -> dict[str, int]:
        """Create separate verified output after the mandatory backup."""
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with closing(
                sqlite3.connect(
                    self.source.as_uri() + "?mode=ro",
                    uri=True,
                )
            ) as source:
                source.row_factory = sqlite3.Row
                source.execute("PRAGMA query_only=ON")
                source.execute("BEGIN")
                self._validate(source)
                counts = self._counts(source)
                with target.open("xb"):
                    created = True
                with closing(sqlite3.connect(target)) as output:
                    output.row_factory = sqlite3.Row
                    source.backup(output)
                    self._apply(output)
                    self._compare(source, output)
            database = SqliteGameDatabase(target)
            database.initialize()
            SqliteMarketStockStore.initialize(database)
            LOGGER.info(
                "Market stock schema upgraded into separate output",
                extra={"event": "state.market_stock_upgraded", "data": counts},
            )
            return counts
        except BaseException:
            if created:
                target.unlink(missing_ok=True)
            raise

    def _validate(self, db: sqlite3.Connection) -> None:
        """Require canonical source guards and valid immutable transports."""
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE name IN "
            "('market_templates','market_offer_templates',"
            "'market_template_uses','market_stock_cursors',"
            "'market_stock_pending','stock_upgrade_offers')"
        ).fetchone():
            raise PersistenceError(
                "Unbekannte Vorratstabellen im Quellschema."
            )
        if (
            list(map(tuple, db.execute("PRAGMA integrity_check"))) != [("ok",)]
            or db.execute("PRAGMA foreign_key_check").fetchone()
            or list(map(tuple, db.execute("SELECT version FROM game_schema")))
            != [("1.1.0",)]
        ):
            raise PersistenceError("Unbekannter oder beschädigter Spielstand.")
        with closing(sqlite3.connect(":memory:")) as reference:
            reference.executescript(PREVIOUS_SCHEMA)
            for kind, name, sql in reference.execute(
                "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL"
            ):
                found = db.execute(
                    "SELECT type,sql FROM sqlite_master WHERE name=?",
                    (name,),
                ).fetchone()
                if (
                    found is None
                    or found[0] != kind
                    or (schema_sql_tokens(found[1]) != schema_sql_tokens(sql))
                ):
                    raise PersistenceError("Quellschema abweichend: " + name)
        for row in db.execute("SELECT * FROM contract_offers"):
            load_offer_record(dict(row))
        for row in db.execute("SELECT * FROM transports"):
            load_transport_record(dict(row))

    def _counts(self, db: sqlite3.Connection) -> dict[str, int]:
        """Report only counts, never player identities or stored documents."""
        return {
            "retained_offers": db.execute(
                "SELECT count(*) FROM contract_offers WHERE expires_at>?",
                (self.now,),
            ).fetchone()[0],
            "expired_offers": db.execute(
                "SELECT count(*) FROM contract_offers WHERE expires_at<=?",
                (self.now,),
            ).fetchone()[0],
            "transports": db.execute(
                "SELECT count(*) FROM transports"
            ).fetchone()[0],
        }

    def _apply(self, db: sqlite3.Connection) -> None:
        """Rebuild only the offer table, preserving live IDs and row order."""
        with closing(sqlite3.connect(":memory:")) as reference:
            reference.executescript(SCHEMA)
            create = reference.execute(
                "SELECT sql FROM sqlite_master WHERE name='contract_offers'"
            ).fetchone()[0]
        rows = list(
            db.execute("SELECT rowid,* FROM contract_offers ORDER BY rowid")
        )
        db.execute("PRAGMA foreign_keys=OFF")
        with db:
            db.execute(
                create.replace("contract_offers", "stock_upgrade_offers", 1)
            )
            for row in rows:
                if row["expires_at"] <= self.now:
                    continue
                raw = json.loads(row["offer_snapshot"])
                raw["data"]["expires_at"] = None
                values = dict(row)
                values["expires_at"] = None
                values["offer_snapshot"] = json.dumps(raw, allow_nan=False)
                db.execute(
                    "INSERT INTO stock_upgrade_offers("
                    "rowid,user_id,contract_id,"
                    "origin_facility_uid,destination_facility_uid,created_at,"
                    "expires_at,market_model,offer_snapshot) VALUES "
                    "(?,?,?,?,?,?,?,?,?)",
                    tuple(values.values()),
                )
            db.execute("DROP TABLE contract_offers")
            db.execute(
                "ALTER TABLE stock_upgrade_offers RENAME TO contract_offers"
            )
            db.execute(
                "CREATE INDEX offers_scope ON contract_offers "
                "(user_id, origin_facility_uid, expires_at)"
            )
            if db.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE name='offer_route_references'"
            ).fetchone():
                db.execute(
                    "DELETE FROM offer_route_references WHERE NOT EXISTS "
                    "(SELECT 1 FROM contract_offers o WHERE "
                    "o.user_id=offer_route_references.user_id AND "
                    "o.contract_id=offer_route_references.contract_id)"
                )
            db.execute("UPDATE game_schema SET version=?", (VERSION,))
        db.execute("PRAGMA foreign_keys=ON")

    def _compare(
        self, source: sqlite3.Connection, target: sqlite3.Connection
    ) -> None:
        """Reconcile all tables and historical JSON before activation."""
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
        expected = []
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
        if expected != list(
            map(
                tuple,
                target.execute(
                    "SELECT rowid,* FROM contract_offers ORDER BY rowid"
                ),
            )
        ):
            raise PersistenceError("Auftragsabgleich fehlgeschlagen.")
        if source.execute(
            "SELECT 1 FROM sqlite_master WHERE name='offer_route_references'"
        ).fetchone():
            expected_refs = list(
                map(
                    tuple,
                    source.execute(
                        "SELECT r.rowid,r.* FROM offer_route_references r "
                        "JOIN "
                        "contract_offers o ON o.user_id=r.user_id AND "
                        "o.contract_id=r.contract_id WHERE o.expires_at>? "
                        "ORDER BY r.rowid",
                        (self.now,),
                    ),
                )
            )
            if expected_refs != list(
                map(
                    tuple,
                    target.execute(
                        "SELECT rowid,* FROM offer_route_references "
                        "ORDER BY rowid"
                    ),
                )
            ):
                raise PersistenceError(
                    "Routenbindungsabgleich fehlgeschlagen."
                )
        if target.execute("PRAGMA foreign_key_check").fetchone() or list(
            map(tuple, target.execute("PRAGMA integrity_check"))
        ) != [("ok",)]:
            raise PersistenceError("Zieldatenbank inkonsistent.")
