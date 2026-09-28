"""Immutable account preferences and their persistence boundary."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AccountPreferences:
    """Effective cosmetic account selection, including legacy fallback."""

    company_color: str


class PreferenceStore(Protocol):
    """Read and persist only authenticated account cosmetic preferences."""

    def transaction(self) -> AbstractContextManager[None]: ...

    def color(self, user_id: str) -> str | None: ...

    def save_color(self, user_id: str, color: str) -> None: ...
