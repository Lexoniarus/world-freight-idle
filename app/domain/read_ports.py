"""Typed public projections independent of account and game write models."""

from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict

from app.domain.routes import RouteLeg


class RankingEntry(TypedDict):
    """Public progress without private economic or authentication data."""

    username: str
    completed: int


@dataclass(frozen=True, slots=True)
class MovementSegment:
    """Public phase and geometry timing, without energy or economic values."""

    phase: Literal["driving", "refuelling", "charging"]
    starts_at: float
    ends_at: float
    start_km: float
    end_km: float


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
    distance_km: float
    segments: tuple[MovementSegment, ...]
    route_legs: tuple[RouteLeg, ...] = ()


class LeaderboardReader(Protocol):
    """Read counters including due but unsettled offline deliveries."""

    def list_ranking(self, active_at: float) -> tuple[RankingEntry, ...]: ...


class TrafficReader(Protocol):
    """Expose public live traffic without private contract snapshots."""

    def list_active_transports(
        self, active_at: float
    ) -> tuple[SharedTransport, ...]: ...
