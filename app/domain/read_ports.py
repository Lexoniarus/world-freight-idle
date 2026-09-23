"""Typed public projections independent of account and game write models."""

from dataclasses import dataclass
from typing import Protocol, TypedDict


class RankingEntry(TypedDict):
    """Public progress without private economic or authentication data."""

    username: str
    completed: int


@dataclass(frozen=True, slots=True)
class SharedTransport:
    """Minimum public transport facts needed by the multiplayer map."""

    user_id: str
    username: str
    id: str
    vehicle_id: str
    model_id: str
    model_name: str
    departed_at: float
    arrives_at: float
    coordinates: tuple[tuple[float, float], ...]


class LeaderboardReader(Protocol):
    """Read counters including due but unsettled offline deliveries."""

    def list_ranking(self, active_at: float) -> tuple[RankingEntry, ...]: ...


class TrafficReader(Protocol):
    """Expose public live traffic without private contract snapshots."""

    def list_active_transports(
        self, active_at: float
    ) -> tuple[SharedTransport, ...]: ...
