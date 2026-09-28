"""Validated immutable vehicle reference cache for one server lifetime."""

import logging
from threading import Lock

from app.domain.ports import VehicleCatalogue
from app.domain.vehicles import VehicleModel

LOGGER = logging.getLogger(__name__)


class CachedVehicleCatalogue:
    """Own a reference cache without introducing catalogue write access."""

    def __init__(self, source: VehicleCatalogue) -> None:
        """Inject the validating source and defer its first read."""
        self.source = source
        self._models: tuple[VehicleModel, ...] | None = None
        self._lock = Lock()

    def list_models(self) -> tuple[VehicleModel, ...]:
        """Reuse one validated revision; failed reads remain retryable."""
        with self._lock:
            if self._models is None:
                self._models = self.source.list_models()
                LOGGER.info(
                    "Vehicle catalogue cached",
                    extra={
                        "event": "vehicle.catalogue_cached",
                        "data": {"models": len(self._models)},
                    },
                )
            return self._models
