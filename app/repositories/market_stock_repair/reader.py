"""Read immutable historical market stock for offline inspection."""

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
from app.repositories.market_stock_repair.validation import (
    MarketStockRepairDatabaseValidator,
)
from app.repositories.snapshot_mapping import load_offer
from app.repositories.state_snapshots import decode_snapshot


class SqliteMarketStockRepairReader:
    """Load repair candidates from one query-only game database."""

    def __init__(self, source: Path) -> None:
        """Bind reads and validation to one explicit source database."""
        self.source = source.resolve()
        self.validator = MarketStockRepairDatabaseValidator(self.source)

    def load_contexts(self) -> tuple[MarketStockRepairContext, ...]:
        """Load bound offers and unused prepared alternatives by context."""
        with closing(
            sqlite3.connect(self.source.as_uri() + "?mode=ro", uri=True)
        ) as database:
            database.row_factory = sqlite3.Row
            database.execute("PRAGMA query_only=ON")
            database.execute("BEGIN")
            self.validator.validate(database)
            templates = self.load_templates(database)
            return self._assemble_contexts(database, templates)

    def load_templates(
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

    def _assemble_contexts(
        self,
        database: sqlite3.Connection,
        templates: tuple[PreparedTemplate, ...],
    ) -> tuple[MarketStockRepairContext, ...]:
        """Group private bindings and available alternatives by scope."""
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
                database.execute("SELECT user_id,contract_id FROM transports"),
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
            offer = load_offer(decode_snapshot("offer", row["offer_snapshot"]))
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
                    and (row["user_id"], row["contract_id"]) not in referenced,
                )
            )
        return tuple(
            MarketStockRepairContext(
                user_id,
                city_uid,
                model_id,
                band,
                tuple(offers),
                self._available_templates(
                    templates,
                    used,
                    bound_by_user[user_id],
                    user_id,
                    city_uid,
                    model_id,
                    band,
                ),
            )
            for (
                user_id,
                city_uid,
                model_id,
                band,
            ), offers in sorted(grouped.items())
        )

    @staticmethod
    def _available_templates(
        templates: tuple[PreparedTemplate, ...],
        used: set[tuple[object, ...]],
        bound: set[str],
        user_id: str,
        city_uid: str,
        model_id: str,
        band: str,
    ) -> tuple[PreparedTemplate, ...]:
        """Filter unused alternatives for one private market scope."""
        return tuple(
            template
            for template in templates
            if template.city_uid == city_uid
            and template.model_id == model_id
            and template.offer.market_context is not None
            and template.offer.market_context.distance_band == band
            and template.template_id not in bound
            and (user_id, template.template_id) not in used
        )
