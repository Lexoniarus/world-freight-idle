"""Private scalar analytics contracts, independent of persistence."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AnalyticsData:
    """One consistent read of current status and historical scalar facts."""

    status: dict[str, Any]
    history: tuple[dict[str, Any], ...]
    ongoing: tuple[dict[str, Any], ...]


class AnalyticsReader(Protocol):
    """Read only the authenticated owner's scalar projections."""

    def read(self, now: float) -> AnalyticsData: ...
