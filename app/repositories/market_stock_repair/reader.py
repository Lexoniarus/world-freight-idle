"""Read immutable historical market stock for offline inspection."""

import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
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

RepairContextKey = tuple[str, str, str, str]
PrivateTemplateKey = tuple[str, str]
PrivateOfferKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _BoundRepairOffer:
    """Carry decoded binding scope into deterministic grouping."""

    city_uid: str
    model_id: str
    distance_band: str
    offer: RepairableMarketOffer


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
            used = self._load_used_template_keys(database)
            referenced = self._load_referenced_offer_keys(database)
            bound_offers = self._load_bound_offers(
                database,
                used,
                referenced,
            )
            grouped = self._group_repairable_offers(bound_offers)
            return self._build_repair_contexts(
                templates,
                used,
                bound_offers,
                grouped,
            )

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

    @staticmethod
    def _load_used_template_keys(
        database: sqlite3.Connection,
    ) -> set[PrivateTemplateKey]:
        """Load private template uses that must never be removed."""
        return {
            (row[0], row[1])
            for row in database.execute(
                "SELECT user_id,template_id FROM market_template_uses"
            )
        }

    @staticmethod
    def _load_referenced_offer_keys(
        database: sqlite3.Connection,
    ) -> set[PrivateOfferKey]:
        """Load offers retained by transport history."""
        return {
            (row[0], row[1])
            for row in database.execute(
                "SELECT user_id,contract_id FROM transports"
            )
        }

    @staticmethod
    def _load_bound_offers(
        database: sqlite3.Connection,
        used: set[PrivateTemplateKey],
        referenced: set[PrivateOfferKey],
    ) -> tuple[_BoundRepairOffer, ...]:
        """Decode bound offers and mark only unreferenced rows removable."""
        records: list[_BoundRepairOffer] = []
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
            template_key = (row["user_id"], row["template_id"])
            offer_key = (row["user_id"], row["contract_id"])
            records.append(
                _BoundRepairOffer(
                    row["city_uid"],
                    row["model_id"],
                    context.distance_band,
                    RepairableMarketOffer(
                        row["user_id"],
                        row["contract_id"],
                        row["template_id"],
                        offer,
                        template_key not in used
                        and offer_key not in referenced,
                    ),
                )
            )
        return tuple(records)

    @staticmethod
    def _group_repairable_offers(
        records: tuple[_BoundRepairOffer, ...],
    ) -> dict[RepairContextKey, tuple[RepairableMarketOffer, ...]]:
        """Group decoded bindings by their private market scope."""
        grouped: dict[
            RepairContextKey,
            list[RepairableMarketOffer],
        ] = defaultdict(list)
        for record in records:
            offer = record.offer
            grouped[
                (
                    offer.user_id,
                    record.city_uid,
                    record.model_id,
                    record.distance_band,
                )
            ].append(offer)
        return {key: tuple(offers) for key, offers in grouped.items()}

    def _build_repair_contexts(
        self,
        templates: tuple[PreparedTemplate, ...],
        used: set[PrivateTemplateKey],
        records: tuple[_BoundRepairOffer, ...],
        grouped: dict[
            RepairContextKey,
            tuple[RepairableMarketOffer, ...],
        ],
    ) -> tuple[MarketStockRepairContext, ...]:
        """Combine grouped bindings with unbound prepared alternatives."""
        bound_by_user: dict[str, set[str]] = defaultdict(set)
        for record in records:
            bound_by_user[record.offer.user_id].add(record.offer.template_id)
        return tuple(
            MarketStockRepairContext(
                user_id,
                city_uid,
                model_id,
                band,
                offers,
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
        used: set[PrivateTemplateKey],
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
