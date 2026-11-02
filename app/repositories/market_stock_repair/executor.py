"""Create and reconcile an offline market-stock repair copy."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from app.domain.errors import PersistenceError
from app.domain.market_stock_repair import MarketStockRepairPlan
from app.repositories.market_stock_repair.archive import (
    MarketStockRepairArchive,
)
from app.repositories.market_stock_repair.validation import (
    MarketStockRepairDatabaseValidator,
    read_table_rows,
)

LOGGER = logging.getLogger(__name__)


class SqliteMarketStockRepairExecutor:
    """Own copy creation, approved mutation and exact reconciliation."""

    def __init__(
        self,
        source: Path,
        archive_writer: MarketStockRepairArchive | None = None,
    ) -> None:
        """Bind repair output to an immutable source and archive writer."""
        self.source = source.resolve()
        self.validator = MarketStockRepairDatabaseValidator(self.source)
        self.archive_writer = archive_writer or MarketStockRepairArchive()

    def create_repaired_copy(
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
        created: list[Path] = []
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
                self.validator.validate(source)
                self._reserve_outputs((target, archive), created)
                with closing(sqlite3.connect(target)) as output:
                    output.row_factory = sqlite3.Row
                    source.backup(output)
                    self.archive_writer.write_repair_archive(
                        source, plan, archive
                    )
                    self.apply_repair_plan(output, plan, now)
                    self.verify_repaired_copy(source, output, plan, now)
            self._log_success(plan)
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            LOGGER.error(
                "Market stock repair rolled back",
                extra={"event": "market.stock_repair_rolled_back"},
            )
            raise

    @staticmethod
    def _reserve_outputs(
        paths: tuple[Path, Path], created: list[Path]
    ) -> None:
        """Reserve new output paths without overwriting existing files."""
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb"):
                pass
            created.append(path)

    @staticmethod
    def apply_repair_plan(
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
                for table in (
                    "market_stock_pending",
                    "market_stock_cursors",
                    "market_coverage",
                ):
                    output.execute(
                        f'DELETE FROM "{table}" WHERE user_id=?',
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

    def verify_repaired_copy(
        self,
        source: sqlite3.Connection,
        output: sqlite3.Connection,
        plan: MarketStockRepairPlan,
        now: float,
    ) -> None:
        """Require exact equality outside the approved repair delta."""
        self._verify_schema(source, output)
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
            if table not in mutable and read_table_rows(
                source, table
            ) != read_table_rows(output, table):
                raise PersistenceError("Unzulässige Marktreparaturänderung.")
        removed = {(item.user_id, item.contract_id) for item in plan.removals}
        affected = {item.user_id for item in plan.removals}
        self._verify_offer_rows(source, output, removed)
        self._verify_progress_rows(source, output, affected)
        self._verify_jobs(source, output, affected, now)
        if output.execute("PRAGMA foreign_key_check").fetchone() or list(
            map(tuple, output.execute("PRAGMA integrity_check"))
        ) != [("ok",)]:
            raise PersistenceError("Reparierte Datenbank inkonsistent.")

    @staticmethod
    def _verify_schema(
        source: sqlite3.Connection,
        output: sqlite3.Connection,
    ) -> None:
        """Require an unchanged schema in the repaired copy."""
        schema = (
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
        )
        if list(map(tuple, source.execute(schema))) != list(
            map(tuple, output.execute(schema))
        ):
            raise PersistenceError("Marktreparaturschema abweichend.")

    @staticmethod
    def _verify_offer_rows(
        source: sqlite3.Connection,
        output: sqlite3.Connection,
        removed: set[tuple[str, str]],
    ) -> None:
        """Require only approved offer identities to be removed."""
        for table in (
            "contract_offers",
            "market_offer_templates",
            "offer_route_references",
        ):
            expected = tuple(
                row
                for row in read_table_rows(source, table)
                if (row[0], row[1]) not in removed
            )
            if expected != read_table_rows(output, table):
                raise PersistenceError("Angebotsbereinigung abweichend.")

    @staticmethod
    def _verify_progress_rows(
        source: sqlite3.Connection,
        output: sqlite3.Connection,
        affected: set[str],
    ) -> None:
        """Require affected player cursors and checkpoints to be reset."""
        for table in (
            "market_stock_pending",
            "market_stock_cursors",
            "market_coverage",
        ):
            expected = tuple(
                row
                for row in read_table_rows(source, table)
                if row[0] not in affected
            )
            if expected != read_table_rows(output, table):
                raise PersistenceError("Marktfortschritt abweichend.")

    @staticmethod
    def _verify_jobs(
        source: sqlite3.Connection,
        output: sqlite3.Connection,
        affected: set[str],
        now: float,
    ) -> None:
        """Require only affected players to receive fresh partial jobs."""
        source_jobs = read_table_rows(source, "market_preparations")
        output_jobs = read_table_rows(output, "market_preparations")
        expected = tuple(row for row in source_jobs if row[0] not in affected)
        if (
            tuple(row for row in output_jobs if row[0] not in affected)
            != expected
        ):
            raise PersistenceError("Unbeteiligte Marktjobs abweichend.")
        repaired = tuple(row for row in output_jobs if row[0] in affected)
        if len(repaired) != len(affected) or any(
            row[3:] != ("partial", None, now) or not row[1] or not row[2]
            for row in repaired
        ):
            raise PersistenceError("Marktjob wurde nicht neu eingereiht.")

    @staticmethod
    def _log_success(plan: MarketStockRepairPlan) -> None:
        """Log aggregate repair facts without private identifiers."""
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
