"""Atomically replace all open markets before accepting requests."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.domain.market_startup import MarketStartupStore
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.services.market_lifecycle import MarketLifecycleService

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MarketStartupService:
    """Own the global rebuild transaction; never settle or create players."""

    store: MarketStartupStore
    world: WorldCatalogue
    catalogue: VehicleCatalogue
    lifecycle: Callable[[str], MarketLifecycleService]

    def rebuild(self) -> None:
        """Validate references, then replace every market or roll back all."""
        self.world.read()
        self.catalogue.list_models()
        owner = None
        try:
            with self.store.transaction():
                for owner in self.store.player_ids():
                    self.lifecycle(owner).refresh(force=True)
        except Exception:
            LOGGER.exception(
                "Startup market rebuild failed",
                extra={
                    "event": "market.startup_failed",
                    "data": {"user_id": owner},
                },
            )
            raise
        LOGGER.info(
            "Startup markets rebuilt", extra={"event": "market.startup"}
        )
