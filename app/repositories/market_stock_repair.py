"""Read historical private market stock for explicit offline correction."""

import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from app.domain.errors import PersistenceError
from app.domain.market_stock import PreparedTemplate
from app.domain.market_stock_repair import (
    MarketStockRepairContext,
    RepairableMarketOffer,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_schema import VERSION
from app.repositories.snapshot_mapping import load_offer
from app.repositories.state_snapshots import decode_snapshot


class SqliteMarketStockRepairStore:
    """Read one immutable game file without owning diversity decisions."""

    def __init__(self, source: Path) -> None:
        """Bind maintenance to one explicit source database."""
        self.source = source.resolve()

    def contexts(self) -> tuple[MarketStockRepairContext, ...]:
        """Load bound offers and unused prepared alternatives by context."""
        with closing(
            sqlite3.connect(self.source.as_uri() + "?mode=ro", uri=True)
        ) as database:
            database.row_factory = sqlite3.Row
            database.execute("PRAGMA query_only=ON")
            database.execute("BEGIN")
            self._validate(database)
            templates = self._templates(database)
            used = set(
                map(
                    tuple,
                    database.execute(
                        "SELECT user_id,template_id FROM market_template_uses"
                    ),
                )
            )
            referenced = set(
                map(
                    tuple,
                    database.execute(
                        "SELECT user_id,contract_id FROM transports"
                    ),
                )
            )
            bound_by_user: dict[str, set[str]] = defaultdict(set)
            grouped: dict[
                tuple[str, str, str, str],
                list[RepairableMarketOffer],
            ] = defaultdict(list)
            rows = database.execute(
                "SELECT binding.user_id,binding.contract_id,"
                "binding.template_id,offer.offer_snapshot,"
                "template.city_uid,template.model_id "
                "FROM market_offer_templates AS binding "
                "JOIN contract_offers AS offer USING(user_id,contract_id) "
                "JOIN market_templates AS template USING(template_id) "
                "ORDER BY binding.user_id,binding.rowid"
            )
            for row in rows:
                offer = load_offer(
                    decode_snapshot("offer", row["offer_snapshot"])
                )
                context = offer.market_context
                if (
                    context is None
                    or row["city_uid"] != offer.origin.city.city_uid
                ):
                    raise PersistenceError("Marktbestand ist nicht lesbar.")
                identity = (row["user_id"], row["template_id"])
                bound_by_user[row["user_id"]].add(row["template_id"])
                grouped[
                    (
                        row["user_id"],
                        row["city_uid"],
                        row["model_id"],
                        context.distance_band,
                    )
                ].append(
                    RepairableMarketOffer(
                        row["user_id"],
                        row["contract_id"],
                        row["template_id"],
                        offer,
                        identity not in used
                        and (row["user_id"], row["contract_id"])
                        not in referenced,
                    )
                )
            return tuple(
                MarketStockRepairContext(
                    user_id,
                    city_uid,
                    model_id,
                    band,
                    tuple(offers),
                    tuple(
                        template
                        for template in templates
                        if template.city_uid == city_uid
                        and template.model_id == model_id
                        and template.offer.market_context is not None
                        and template.offer.market_context.distance_band == band
                        and template.template_id not in bound_by_user[user_id]
                        and (user_id, template.template_id) not in used
                    ),
                )
                for (
                    user_id,
                    city_uid,
                    model_id,
                    band,
                ), offers in sorted(grouped.items())
            )

    def _templates(
        self, database: sqlite3.Connection
    ) -> tuple[PreparedTemplate, ...]:
        """Decode shared templates once for all private contexts."""
        return tuple(
            PreparedTemplate(
                row["template_id"],
                row["model_id"],
                row["city_uid"],
                load_offer(decode_snapshot("offer", row["offer_snapshot"])),
            )
            for row in database.execute(
                "SELECT * FROM market_templates ORDER BY rowid"
            )
        )

    def _validate(self, database: sqlite3.Connection) -> None:
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
        if (
            not required <= present
            or list(
                map(
                    tuple,
                    database.execute("SELECT version FROM game_schema"),
                )
            )
            != [(VERSION,)]
            or list(map(tuple, database.execute("PRAGMA integrity_check")))
            != [("ok",)]
            or database.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise PersistenceError("Spielstandintegrität abweichend.")
        SqliteGameDatabase(self.source)._validate_structure(database)
