"""Aggregate private historical facts without changing game state."""

import logging
from datetime import UTC, date, datetime, timedelta

from app.domain.analytics import (
    AnalyticsDay,
    AnalyticsGroup,
    AnalyticsReader,
    AnalyticsResult,
    AnalyticsSummary,
    AnalyticsTransport,
)
from app.domain.analytics_labels import vehicle_labels
from app.domain.market_profiles import DISTANCE_BANDS, TRANSPORT_CLASSES

LOGGER = logging.getLogger(__name__)
METRICS = (
    "revenue_eur",
    "operating_cost_eur",
    "profit_eur",
    "distance_km",
    "tons",
)
SCOPES = ("company", "city", "vehicle", "transport_class", "distance_band")


def validate_scope(days: str, scope: str, scope_id: str | None) -> None:
    """Reject unsupported selectors before reading private data."""
    if (
        days not in {"7", "30", "90", "all"}
        or scope not in SCOPES
        or (scope == "company" and scope_id is not None)
        or (scope != "company" and not scope_id)
        or (scope == "transport_class" and scope_id not in TRANSPORT_CLASSES)
        or (scope == "distance_band" and scope_id not in DISTANCE_BANDS)
    ):
        raise ValueError("Ungültiger Statistikzeitraum oder Scope.")


def summarize(rows: list[AnalyticsTransport]) -> AnalyticsSummary:
    """Compute additive performance and defined ratios."""
    revenue = sum(row.revenue_eur for row in rows)
    costs = sum(row.operating_cost_eur for row in rows)
    profit = sum(row.profit_eur for row in rows)
    distance = sum(row.distance_km for row in rows)
    tons = sum(row.tons for row in rows)
    return AnalyticsSummary(
        revenue,
        costs,
        profit,
        distance,
        tons,
        len(rows),
        profit / len(rows) if rows else None,
        revenue / distance if distance else None,
        tons / len(rows) if rows else None,
    )


def dimension_value(row: AnalyticsTransport, dimension: str) -> str | None:
    """Select a supported historical dimension without dynamic fields."""
    return {
        "city": row.city,
        "vehicle": row.vehicle_id,
        "transport_class": row.transport_class,
        "distance_band": row.distance_band,
    }[dimension]


def breakdown(
    rows: list[AnalyticsTransport],
    dimension: str,
    labels: dict[str, str] | None = None,
) -> tuple[AnalyticsGroup, ...]:
    """Group history without joining today's vehicle models."""
    groups: dict[str, list[AnalyticsTransport]] = {}
    for row in rows:
        value = dimension_value(row, dimension)
        if value is not None:
            groups.setdefault(value, []).append(row)
    return tuple(
        AnalyticsGroup(
            key,
            group[-1].city_name
            if dimension == "city"
            else (labels or {}).get(key, key),
            summarize(group),
        )
        for key, group in sorted(groups.items())
    )


def select_scope_rows(
    rows: tuple[AnalyticsTransport, ...],
    scope: str,
    scope_id: str | None,
) -> list[AnalyticsTransport]:
    """Select historical rows for one validated analytics scope."""
    return [
        row
        for row in rows
        if scope == "company" or dimension_value(row, scope) == scope_id
    ]


def analytics_start_date(
    rows: list[AnalyticsTransport],
    today: date,
    days: str,
) -> date:
    """Resolve the inclusive UTC start date for one analytics period."""
    if days == "all":
        return (
            datetime.fromtimestamp(rows[0].arrives_at, UTC).date()
            if rows
            else today
        )
    return today - timedelta(days=int(days) - 1)


def select_period_rows(
    rows: list[AnalyticsTransport],
    start: date,
) -> list[AnalyticsTransport]:
    """Select rows at or after one inclusive UTC day boundary."""
    boundary = datetime.combine(start, datetime.min.time(), UTC).timestamp()
    return [row for row in rows if row.arrives_at >= boundary]


def build_daily_series(
    rows: list[AnalyticsTransport],
    start: date,
    today: date,
) -> tuple[AnalyticsDay, ...]:
    """Build a gap-free UTC series for already selected rows."""
    by_day: dict[str, list[AnalyticsTransport]] = {}
    for row in rows:
        day = datetime.fromtimestamp(row.arrives_at, UTC).date().isoformat()
        by_day.setdefault(day, []).append(row)
    series: list[AnalyticsDay] = []
    for offset in range((today - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        series.append(AnalyticsDay(day, summarize(by_day.get(day, []))))
    return tuple(series)


class AnalyticsService:
    """Compose current status, scoped history, UTC series and breakdowns."""

    def __init__(self, reader: AnalyticsReader) -> None:
        """Inject a consistent scalar reader."""
        self.reader = reader

    def analyze(
        self,
        now: float,
        days: str,
        scope: str,
        scope_id: str | None,
    ) -> AnalyticsResult:
        """Read once and aggregate without invoking a write repository."""
        validate_scope(days, scope, scope_id)
        data = self.reader.read(now)
        labels = vehicle_labels(
            data.vehicle_names,
            tuple(row.vehicle_id for row in data.history)
            + tuple(row.vehicle_id for row in data.ongoing),
        )
        rows = select_scope_rows(data.history, scope, scope_id)
        today = datetime.fromtimestamp(now, UTC).date()
        start = analytics_start_date(rows, today, days)
        selected = select_period_rows(rows, start)
        series = build_daily_series(selected, start, today) if rows else ()
        LOGGER.info(
            "Company analytics read",
            extra={
                "event": "company.analytics.read",
                "data": {"scope": scope, "days": days, "rows": len(selected)},
            },
        )
        return AnalyticsResult(
            now,
            days,
            start.isoformat(),
            today.isoformat(),
            scope,
            scope_id,
            data.status,
            summarize(rows),
            summarize(selected),
            series,
            tuple(
                (
                    key,
                    breakdown(
                        selected, key, labels if key == "vehicle" else None
                    ),
                )
                for key in SCOPES[1:]
            ),
            tuple((row, labels[row.vehicle_id]) for row in data.ongoing),
            len(data.history),
            sum(row.market_model == "nhm_v2" for row in selected),
            sum(row.market_model != "nhm_v2" for row in selected),
        )
