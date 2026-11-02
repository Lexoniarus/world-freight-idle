"""Read-only validation of legacy market-stock databases."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass

from app.domain.errors import PersistenceError
from app.repositories.game_database import schema_sql_tokens
from app.repositories.game_state import (
    load_offer_record,
    load_transport_record,
)
from app.repositories.previous_game_schema import SCHEMA as PREVIOUS_SCHEMA


@dataclass(frozen=True, slots=True)
class MarketStockUpgradeInspector:
    """Validate the supported source schema and summarize its contents."""

    now: float

    def validate(self, database: sqlite3.Connection) -> None:
        """Require canonical source guards and valid immutable transports."""
        if database.execute(
            "SELECT 1 FROM sqlite_master WHERE name IN "
            "('market_templates','market_offer_templates',"
            "'market_template_uses','market_stock_cursors',"
            "'market_stock_pending','stock_upgrade_offers')"
        ).fetchone():
            raise PersistenceError(
                "Unbekannte Vorratstabellen im Quellschema."
            )
        if (
            list(map(tuple, database.execute("PRAGMA integrity_check")))
            != [("ok",)]
            or database.execute("PRAGMA foreign_key_check").fetchone()
            or list(
                map(
                    tuple,
                    database.execute("SELECT version FROM game_schema"),
                )
            )
            != [("1.1.0",)]
        ):
            raise PersistenceError("Unbekannter oder beschädigter Spielstand.")
        with closing(sqlite3.connect(":memory:")) as reference:
            reference.executescript(PREVIOUS_SCHEMA)
            for kind, name, sql in reference.execute(
                "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL"
            ):
                found = database.execute(
                    "SELECT type,sql FROM sqlite_master WHERE name=?",
                    (name,),
                ).fetchone()
                if (
                    found is None
                    or found[0] != kind
                    or schema_sql_tokens(found[1]) != schema_sql_tokens(sql)
                ):
                    raise PersistenceError("Quellschema abweichend: " + name)
        for row in database.execute("SELECT * FROM contract_offers"):
            load_offer_record(dict(row))
        for row in database.execute("SELECT * FROM transports"):
            load_transport_record(dict(row))

    def counts(self, database: sqlite3.Connection) -> dict[str, int]:
        """Report only counts, never player identities or documents."""
        return {
            "retained_offers": database.execute(
                "SELECT count(*) FROM contract_offers WHERE expires_at>?",
                (self.now,),
            ).fetchone()[0],
            "expired_offers": database.execute(
                "SELECT count(*) FROM contract_offers WHERE expires_at<=?",
                (self.now,),
            ).fetchone()[0],
            "transports": database.execute(
                "SELECT count(*) FROM transports"
            ).fetchone()[0],
        }
