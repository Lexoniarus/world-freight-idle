"""Offline migration contract; never used by the game runtime."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExcludedOffer:
    """Explicit record of an intact offer which is no longer playable."""

    user_id: str
    contract_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class GameImportReport:
    """Reconciliation counts without credentials or player balances."""

    accounts: int
    vehicles: int
    offers: int
    transports: int
    excluded_offers: tuple[ExcludedOffer, ...]


class GameStateImporter(Protocol):
    """Inspect an offline source and create a separate reconciled target."""

    def inspect(self, now: float) -> GameImportReport: ...

    def import_to(self, target: Path, now: float) -> GameImportReport: ...
