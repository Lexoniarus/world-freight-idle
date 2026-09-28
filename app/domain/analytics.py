"""Immutable scalar analytics contracts, independent of persistence."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AnalyticsStatus:
    """Describe current company state from one consistent read."""

    cash: int
    completed: int
    reputation: int
    vehicles: int
    idle_vehicles: int
    enroute_vehicles: int
    active_cities: int
    active_transports: int


@dataclass(frozen=True, slots=True)
class AnalyticsTransport:
    """Retain historical scalar facts without reconstructing routes."""

    transport_id: str
    vehicle_id: str
    arrives_at: float
    revenue_eur: int
    operating_cost_eur: int
    profit_eur: int
    distance_km: float
    tons: float
    city: str
    city_name: str
    market_model: str
    transport_class: str | None
    distance_band: str | None


@dataclass(frozen=True, slots=True)
class AnalyticsOngoing:
    """Describe booked amounts of one ongoing transport."""

    vehicle_id: str
    revenue_eur: int
    operating_cost_eur: int
    profit_eur: int


@dataclass(frozen=True, slots=True)
class AnalyticsData:
    """One consistent read of current and historical scalar facts."""

    status: AnalyticsStatus
    history: tuple[AnalyticsTransport, ...]
    ongoing: tuple[AnalyticsOngoing, ...]
    vehicle_names: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    """Aggregate additive metrics and defined performance ratios."""

    revenue_eur: int
    operating_cost_eur: int
    profit_eur: int
    distance_km: float
    tons: float
    completed_transports: int
    profit_per_transport: float | None
    revenue_per_km: float | None
    tons_per_transport: float | None


@dataclass(frozen=True, slots=True)
class AnalyticsGroup:
    """Associate a historical dimension with its display label and totals."""

    id: str
    label: str
    summary: AnalyticsSummary


@dataclass(frozen=True, slots=True)
class AnalyticsDay:
    """Associate a UTC calendar date with its aggregate metrics."""

    date: str
    summary: AnalyticsSummary


@dataclass(frozen=True, slots=True)
class AnalyticsResult:
    """Return calculated company performance without HTTP field mapping."""

    server_time: float
    days: str
    start_date: str
    end_date: str
    scope: str
    scope_id: str | None
    status: AnalyticsStatus
    totals: AnalyticsSummary
    period_totals: AnalyticsSummary
    daily: tuple[AnalyticsDay, ...]
    breakdowns: tuple[tuple[str, tuple[AnalyticsGroup, ...]], ...]
    ongoing: tuple[tuple[AnalyticsOngoing, str], ...]
    recorded_transports: int
    v2_transports: int
    unclassified_transports: int


class AnalyticsReader(Protocol):
    """Read only the authenticated owner's scalar projections."""

    def read(self, now: float) -> AnalyticsData: ...
