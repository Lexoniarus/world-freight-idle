"""Read and copy historical market stock for offline correction."""

import json
import logging
import sqlite3
from collections import defaultdict
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.domain.errors import PersistenceError
from app.domain.market_stock import PreparedTemplate
from app.domain.market_stock_repair import (
    MarketStockRepairContext,
    MarketStockRepairPlan,
    RepairableMarketOffer,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_schema import VERSION
from app.repositories.snapshot_mapping import load_offer
from app.repositories.state_snapshots import decode_snapshot

LOGGER = logging.getLogger(__name__)


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

    def repair_to(
        self,
        plan: MarketStockRepairPlan,
        target: Path,
        archive: Path,
        now: float,
    ) -> None:
        """Create, mutate and reconcile a separate database copy."""
        target, archive = target.resolve(), archive.resolve()
        if len({self.source, target, archive}) != 3:
            raise ValueError("Source, target and archive must differ.")
        created = []
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
                for path in (target, archive):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb"):
                        pass
                    created.append(path)
                with closing(sqlite3.connect(target)) as output:
                    output.row_factory = sqlite3.Row
                    source.backup(output)
                    self._archive(source, plan, archive)
                    self._apply(output, plan, now)
                    self._compare(source, output, plan, now)
            LOGGER.info(
                "Market stock repaired in a verified offline copy",
                extra={
                    "event": "market.stock_copy_repaired",
                    "data": {
                        "removed_offers": len(plan.removals),
                        "requeued_players": len(
                            {item.user_id for item in plan.removals}
                        ),
                    },
                },
            )
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            LOGGER.error(
                "Market stock repair rolled back",
                extra={"event": "market.stock_repair_rolled_back"},
            )
            raise

    def _archive(
        self,
        source: sqlite3.Connection,
        plan: MarketStockRepairPlan,
        archive: Path,
    ) -> None:
        """Archive every removed or reset row with a payload checksum."""
        records = []
        for removal in plan.removals:
            payload = {
                "repair_version": 1,
                "kind": "offer",
                "user_id": removal.user_id,
                "contract_id": removal.contract_id,
                "tables": {
                    "contract_offers": self._selected_records(
                        source,
                        "contract_offers",
                        "user_id=? AND contract_id=?",
                        (removal.user_id, removal.contract_id),
                    ),
                    "market_offer_templates": self._selected_records(
                        source,
                        "market_offer_templates",
                        "user_id=? AND contract_id=?",
                        (removal.user_id, removal.contract_id),
                    ),
                    "offer_route_references": self._selected_records(
                        source,
                        "offer_route_references",
                        "user_id=? AND contract_id=?",
                        (removal.user_id, removal.contract_id),
                    ),
                },
            }
            records.append(self._checked_record(payload))
        for user_id in sorted({item.user_id for item in plan.removals}):
            payload = {
                "repair_version": 1,
                "kind": "player_reset",
                "user_id": user_id,
                "tables": {
                    table: self._selected_records(
                        source,
                        table,
                        "user_id=?",
                        (user_id,),
                    )
                    for table in (
                        "market_stock_pending",
                        "market_stock_cursors",
                        "market_preparations",
                        "market_coverage",
                    )
                },
            }
            records.append(self._checked_record(payload))
        archive.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for record in records
            ),
            encoding="utf-8",
            newline="\n",
        )
        for line in archive.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            checksum = record.pop("sha256")
            if (
                checksum
                != sha256(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
            ):
                raise PersistenceError("Marktreparaturarchiv abweichend.")

    def _apply(
        self,
        output: sqlite3.Connection,
        plan: MarketStockRepairPlan,
        now: float,
    ) -> None:
        """Apply only planned deletions and player refill resets."""
        users = sorted({item.user_id for item in plan.removals})
        output.execute("PRAGMA foreign_keys=ON")
        with output:
            output.executemany(
                "DELETE FROM contract_offers "
                "WHERE user_id=? AND contract_id=?",
                ((item.user_id, item.contract_id) for item in plan.removals),
            )
            for user_id in users:
                output.execute(
                    "DELETE FROM market_stock_pending WHERE user_id=?",
                    (user_id,),
                )
                output.execute(
                    "DELETE FROM market_stock_cursors WHERE user_id=?",
                    (user_id,),
                )
                output.execute(
                    "DELETE FROM market_coverage WHERE user_id=?",
                    (user_id,),
                )
                output.execute(
                    "INSERT INTO market_preparations VALUES "
                    "(?, ?, ?, 'partial', NULL, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET "
                    "preparation_id=excluded.preparation_id, "
                    "generation=excluded.generation, status='partial', "
                    "next_retry_at=NULL, updated_at=excluded.updated_at",
                    (user_id, uuid4().hex, uuid4().hex, now),
                )

    def _compare(
        self,
        source: sqlite3.Connection,
        output: sqlite3.Connection,
        plan: MarketStockRepairPlan,
        now: float,
    ) -> None:
        """Require exact equality outside the approved repair delta."""
        schema = (
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
        )
        if list(map(tuple, source.execute(schema))) != list(
            map(tuple, output.execute(schema))
        ):
            raise PersistenceError("Marktreparaturschema abweichend.")
        mutable = {
            "contract_offers",
            "market_offer_templates",
            "offer_route_references",
            "market_stock_pending",
            "market_stock_cursors",
            "market_preparations",
            "market_coverage",
        }
        tables = tuple(
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        )
        for table in tables:
            if table not in mutable and self._records(
                source, table
            ) != self._records(output, table):
                raise PersistenceError("Unzulässige Marktreparaturänderung.")
        removed = {(item.user_id, item.contract_id) for item in plan.removals}
        affected = {item.user_id for item in plan.removals}
        for table in (
            "contract_offers",
            "market_offer_templates",
            "offer_route_references",
        ):
            expected = tuple(
                row
                for row in self._records(source, table)
                if (row[0], row[1]) not in removed
            )
            if expected != self._records(output, table):
                raise PersistenceError("Angebotsbereinigung abweichend.")
        for table in (
            "market_stock_pending",
            "market_stock_cursors",
            "market_coverage",
        ):
            expected = tuple(
                row
                for row in self._records(source, table)
                if row[0] not in affected
            )
            if expected != self._records(output, table):
                raise PersistenceError("Marktfortschritt abweichend.")
        expected_jobs = tuple(
            row
            for row in self._records(source, "market_preparations")
            if row[0] not in affected
        )
        actual_jobs = self._records(output, "market_preparations")
        if (
            tuple(row for row in actual_jobs if row[0] not in affected)
            != expected_jobs
        ):
            raise PersistenceError("Unbeteiligte Marktjobs abweichend.")
        repaired_jobs = tuple(row for row in actual_jobs if row[0] in affected)
        if len(repaired_jobs) != len(affected) or any(
            row[3:] != ("partial", None, now) or not row[1] or not row[2]
            for row in repaired_jobs
        ):
            raise PersistenceError("Marktjob wurde nicht neu eingereiht.")
        if output.execute("PRAGMA foreign_key_check").fetchone() or list(
            map(tuple, output.execute("PRAGMA integrity_check"))
        ) != [("ok",)]:
            raise PersistenceError("Reparierte Datenbank inkonsistent.")

    def _selected_records(
        self,
        database: sqlite3.Connection,
        table: str,
        where: str,
        parameters: tuple[str, ...],
    ) -> list[dict[str, object]]:
        """Read explicit rows for the private rollback archive."""
        return [
            dict(row)
            for row in database.execute(
                f'SELECT * FROM "{table}" WHERE {where} ORDER BY rowid',
                parameters,
            )
        ]

    def _records(
        self,
        database: sqlite3.Connection,
        table: str,
    ) -> tuple[tuple[object, ...], ...]:
        """Read stable full-table values for reconciliation."""
        return tuple(
            map(
                tuple,
                database.execute(f'SELECT * FROM "{table}" ORDER BY rowid'),
            )
        )

    def _checked_record(self, payload: dict[str, object]) -> dict[str, object]:
        """Attach a canonical checksum without logging archive contents."""
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return {**payload, "sha256": sha256(encoded).hexdigest()}
