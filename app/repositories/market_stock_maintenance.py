"""Plan and apply explicit duplicate market-stock maintenance."""

from __future__ import annotations

import json
import uuid
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.domain.market_stock import (
    MarketStockRepairPlan,
    PreparedTemplate,
    StockScope,
    TradeKey,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.market_stock import _load_template


class MarketStockMaintenanceRepository:
    """Own narrow SQL and reconciliation for an operator-run cleanup."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Inject the existing transactional runtime boundary."""
        self.database = database

    def duplicate_scopes(self) -> tuple[StockScope, ...]:
        """Find scopes containing repeated unconsumed trade templates."""
        templates = self._templates()
        counts: dict[tuple[StockScope, TradeKey], int] = {}
        for template in templates:
            key = (self._scope(template), self._trade(template))
            counts[key] = counts.get(key, 0) + 1
        return tuple(
            sorted(
                {scope for (scope, _), count in counts.items() if count > 1}
            )
        )

    def inspect(
        self, repairable_scopes: frozenset[StockScope]
    ) -> MarketStockRepairPlan:
        """Compute a deterministic deletion plan without writing."""
        templates = self._templates()
        by_id = {template.template_id: template for template in templates}
        with self.database.read_transaction(), self.database.connect() as db:
            bindings = tuple(
                map(
                    tuple,
                    db.execute(
                        "SELECT user_id, contract_id, template_id FROM "
                        "market_offer_templates ORDER BY user_id, contract_id"
                    ),
                )
            )
            used = {
                row[0]
                for row in db.execute(
                    "SELECT template_id FROM market_template_uses"
                )
            }
        grouped: dict[
            tuple[str, StockScope, TradeKey], list[tuple[str, str, str]]
        ] = {}
        for user_id, contract_id, template_id in bindings:
            template = by_id[template_id]
            scope = self._scope(template)
            if scope not in repairable_scopes:
                continue
            grouped.setdefault(
                (user_id, scope, self._trade(template)), []
            ).append((user_id, contract_id, template_id))
        offers = tuple(
            sorted(
                (user_id, contract_id)
                for rows in grouped.values()
                for user_id, contract_id, _ in sorted(rows)[1:]
            )
        )
        removed_offers = set(offers)
        remaining_bound = {
            template_id
            for user_id, contract_id, template_id in bindings
            if (user_id, contract_id) not in removed_offers
        }
        protected = remaining_bound | used
        protected_keys = {
            (self._scope(by_id[template_id]), self._trade(by_id[template_id]))
            for template_id in protected
        }
        reusable: dict[tuple[StockScope, TradeKey], list[str]] = {}
        for template in templates:
            scope = self._scope(template)
            if (
                template.template_id in protected
                or scope not in repairable_scopes
            ):
                continue
            reusable.setdefault((scope, self._trade(template)), []).append(
                template.template_id
            )
        template_ids = tuple(
            sorted(
                template_id
                for key, values in reusable.items()
                for template_id in sorted(values)[
                    0 if key in protected_keys else 1 :
                ]
            )
        )
        users = tuple(sorted({user_id for user_id, _ in offers}))
        affected_scopes = tuple(
            sorted(
                {
                    self._scope(by_id[template_id])
                    for user_id, contract_id, template_id in bindings
                    if (user_id, contract_id) in removed_offers
                }
                | {
                    self._scope(by_id[template_id])
                    for template_id in template_ids
                }
            )
        )
        return MarketStockRepairPlan(
            affected_scopes,
            offers,
            template_ids,
            users,
        )

    def apply(
        self,
        plan: MarketStockRepairPlan,
        archive: Path,
        now: float,
    ) -> dict[str, int | str]:
        """Archive, mutate atomically and prove protected state unchanged."""
        archive = archive.resolve()
        if archive.exists():
            raise ValueError("Archive path must be new.")
        protected = self._protected_digest()
        archive_digest = self._write_archive(plan, archive)
        try:
            with self.database.transaction(), self.database.connect() as db:
                for user_id, contract_id in plan.offers:
                    cursor = db.execute(
                        "DELETE FROM contract_offers WHERE user_id=? "
                        "AND contract_id=?",
                        (user_id, contract_id),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("Market offer cleanup diverged.")
                for template_id in plan.templates:
                    cursor = db.execute(
                        "DELETE FROM market_templates WHERE template_id=? "
                        "AND NOT EXISTS (SELECT 1 FROM "
                        "market_offer_templates WHERE template_id=?) "
                        "AND NOT EXISTS (SELECT 1 FROM "
                        "market_template_uses WHERE template_id=?)",
                        (template_id, template_id, template_id),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("Market template cleanup diverged.")
                for user_id in plan.users:
                    db.execute(
                        "DELETE FROM market_stock_pending WHERE user_id=?",
                        (user_id,),
                    )
                    db.execute(
                        "DELETE FROM market_stock_cursors WHERE user_id=?",
                        (user_id,),
                    )
                    db.execute(
                        "DELETE FROM market_coverage WHERE user_id=?",
                        (user_id,),
                    )
                    db.execute(
                        "UPDATE market_preparations SET generation=?, "
                        "status='partial', next_retry_at=NULL, updated_at=? "
                        "WHERE user_id=?",
                        (uuid.uuid4().hex, now, user_id),
                    )
                if self._protected_digest() != protected:
                    raise ValueError("Protected game state changed.")
        except BaseException:
            archive.unlink(missing_ok=True)
            raise
        report: dict[str, int | str] = {
            key: value for key, value in plan.report().items()
        }
        report["archive_sha256"] = archive_digest
        return report

    def _templates(self) -> tuple[PreparedTemplate, ...]:
        """Load immutable template documents in deterministic order."""
        with self.database.read_transaction(), self.database.connect() as db:
            rows = db.execute(
                "SELECT * FROM market_templates ORDER BY rowid"
            ).fetchall()
        return tuple(_load_template(row) for row in rows)

    def _write_archive(
        self, plan: MarketStockRepairPlan, archive: Path
    ) -> str:
        """Write a private reconciliation archive before destructive work."""
        data: dict[str, list[dict[str, Any]]] = {}
        with self.database.read_transaction(), self.database.connect() as db:
            for table in (
                "contract_offers",
                "market_offer_templates",
                "offer_route_references",
                "market_stock_pending",
                "market_stock_cursors",
                "market_preparations",
                "market_coverage",
            ):
                data[table] = [
                    dict(row)
                    for row in db.execute(
                        f"SELECT * FROM {table} WHERE user_id IN "
                        "(SELECT value FROM json_each(?))",
                        (json.dumps(plan.users),),
                    )
                ]
            data["market_templates"] = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM market_templates WHERE template_id IN "
                    "(SELECT value FROM json_each(?))",
                    (json.dumps(plan.templates),),
                )
            ]
        payload = json.dumps(
            data,
            allow_nan=False,
            default=str,
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = sha256(payload.encode()).hexdigest()
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(
                {"sha256": digest, "data": data},
                output,
                allow_nan=False,
                default=str,
                sort_keys=True,
            )
            output.write("\n")
        return digest

    def _protected_digest(self) -> str:
        """Fingerprint gameplay and consumption rows excluded from cleanup."""
        documents = []
        with self.database.read_transaction(), self.database.connect() as db:
            for table, order in (
                ("player_states", "user_id"),
                ("owned_vehicles", "user_id, vehicle_id"),
                ("transports", "user_id, transport_id"),
                ("market_template_uses", "user_id, template_id"),
            ):
                documents.append(
                    (
                        table,
                        [
                            dict(row)
                            for row in db.execute(
                                f"SELECT * FROM {table} ORDER BY {order}"
                            )
                        ],
                    )
                )
        return sha256(
            json.dumps(
                documents,
                allow_nan=False,
                default=str,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()

    @staticmethod
    def _scope(template: PreparedTemplate) -> StockScope:
        """Project one template's stable stock grouping."""
        assert template.offer.market_context is not None
        return (
            template.city_uid,
            template.model_id,
            template.offer.market_context.distance_band,
        )

    @staticmethod
    def _trade(template: PreparedTemplate) -> TradeKey:
        """Project one template's exact reusable trade identity."""
        return (
            template.offer.origin.facility_uid,
            template.offer.destination.facility_uid,
            template.offer.cargo.nhm_row_id,
        )
