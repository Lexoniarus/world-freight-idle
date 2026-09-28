"""Reconcile business state before reading an independent compact snapshot."""

from dataclasses import dataclass

from app.domain.runtime_views import RuntimeReader, RuntimeView
from app.services.game import GameService


@dataclass(slots=True)
class RuntimeViewService:
    """Keep read projection separate from game mutations and road downloads."""

    game: GameService
    reader: RuntimeReader
    user_id: str

    def read(self) -> RuntimeView:
        """Settle due arrivals once, then read the private snapshot."""
        self.game.reconcile_arrival()
        return RuntimeView(
            self.reader.read(self.user_id),
            self.game.now(),
            self.game.time_scale,
            self.game.preparation_status(),
        )
