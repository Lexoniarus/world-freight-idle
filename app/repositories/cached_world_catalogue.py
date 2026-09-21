"""Runtime cache for the immutable world reference catalogue."""

from __future__ import annotations

import logging
from threading import Lock

from app.domain.ports import WorldCatalogue
from app.domain.world import WorldSnapshot

LOGGER = logging.getLogger(__name__)


class CachedWorldCatalogue:
    """Load one immutable world revision and reuse it for runtime reads."""

    def __init__(self, source: WorldCatalogue) -> None:
        self.source = source
        self._snapshot: WorldSnapshot | None = None
        self._lock = Lock()

    def read(self) -> WorldSnapshot:
        """Return the cached snapshot, loading it exactly once when needed."""
        snapshot = self._snapshot
        if snapshot is not None:
            return snapshot
        with self._lock:
            if self._snapshot is None:
                self._snapshot = self.source.read()
                LOGGER.info(
                    "World catalogue cached",
                    extra={
                        "event": "world.catalogue_cached",
                        "data": {
                            "catalogue_version": self._snapshot.version,
                            "facilities": len(self._snapshot.facilities),
                        },
                    },
                )
            return self._snapshot
