"""Immutable evidence shared by reference facts and historical values."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Evidence retained with a reference fact."""

    url: str
    role: str
    verified_at: str | None
    precision: str | None = None
    provider: str | None = None
