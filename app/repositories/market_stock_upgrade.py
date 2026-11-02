"""Offline market-stock upgrade orchestration."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from app.repositories.game_database import SqliteGameDatabase
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_stock_upgrade_inspection import (
    MarketStockUpgradeInspector,
)
from app.repositories.market_stock_upgrade_reconciliation import (
    MarketStockUpgradeReconciler,
)
from app.repositories.market_stock_upgrade_transformation import (
    MarketStockUpgradeTransformer,
)
from app.repositories.market_templates import SqliteMarketTemplateStore

LOGGER = logging.getLogger(__name__)


class MarketStockUpgradeRepository:
    """Coordinate read-only inspection, transformation and reconciliation."""

    def __init__(self, source: Path, now: float) -> None:
        """Bind an explicit source and one consistent upgrade cutoff."""
        self.source = source.resolve()
        self.inspector = MarketStockUpgradeInspector(now)
        self.transformer = MarketStockUpgradeTransformer(now)
        self.reconciler = MarketStockUpgradeReconciler(now)

    def inspect(self) -> dict[str, int]:
        """Validate without opening the source for writing."""
        with self._open_source() as database:
            self.inspector.validate(database)
            return self.inspector.counts(database)

    def upgrade_to(self, target: Path) -> dict[str, int]:
        """Create separate verified output after the mandatory backup."""
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with self._open_source() as source:
                self.inspector.validate(source)
                counts = self.inspector.counts(source)
                with target.open("xb"):
                    created = True
                with closing(sqlite3.connect(target)) as output:
                    output.row_factory = sqlite3.Row
                    source.backup(output)
                    self.transformer.apply(output)
                    self.reconciler.validate(source, output)
            database = SqliteGameDatabase(target)
            database.initialize()
            SqliteMarketTemplateStore.initialize(database)
            SqlitePlayerMarketStockStore.initialize(database)
            LOGGER.info(
                "Market stock schema upgraded into separate output",
                extra={"event": "state.market_stock_upgraded", "data": counts},
            )
            return counts
        except BaseException:
            if created:
                target.unlink(missing_ok=True)
            raise

    def _open_source(self) -> closing[sqlite3.Connection]:
        """Open one immutable source transaction with named row access."""
        database = sqlite3.connect(
            self.source.as_uri() + "?mode=ro",
            uri=True,
        )
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA query_only=ON")
        database.execute("BEGIN")
        return closing(database)
