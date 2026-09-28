"""Ports for an all-player market rebuild before server readiness."""

from contextlib import AbstractContextManager
from typing import Protocol


class MarketStartupStore(Protocol):
    """Global transaction and existing profile inventory only."""

    def transaction(self) -> AbstractContextManager[None]: ...

    def player_ids(self) -> tuple[str, ...]: ...
