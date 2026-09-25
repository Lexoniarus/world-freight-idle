"""Aggregate private historical facts without changing game state."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.analytics import AnalyticsReader
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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute additive performance and defined ratios."""
    result = {key: sum(row[key] for row in rows) for key in METRICS}
    result["completed_transports"] = len(rows)
    return {
        **result,
        "profit_per_transport": result["profit_eur"] / len(rows)
        if rows
        else None,
        "revenue_per_km": result["revenue_eur"] / result["distance_km"]
        if result["distance_km"]
        else None,
        "tons_per_transport": result["tons"] / len(rows) if rows else None,
    }


def breakdown(
    rows: list[dict[str, Any]], dimension: str
) -> list[dict[str, Any]]:
    """Group historical identifiers without joining today's vehicle models."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row[dimension] is not None:
            groups.setdefault(row[dimension], []).append(row)
    return [
        {
            "id": key,
            "label": group[-1]["city_name"] if dimension == "city" else key,
            **summarize(group),
        }
        for key, group in sorted(groups.items())
    ]


class AnalyticsService:
    """Compose current status, scoped history, UTC series and breakdowns."""

    def __init__(self, reader: AnalyticsReader) -> None:
        self.reader = reader

    def analyze(
        self,
        now: float,
        days: str,
        scope: str,
        scope_id: str | None,
    ) -> dict[str, Any]:
        """Read once and aggregate without invoking a write repository."""
        validate_scope(days, scope, scope_id)
        data = self.reader.read(now)
        rows = [
            row
            for row in data.history
            if scope == "company" or row[scope] == scope_id
        ]
        today = datetime.fromtimestamp(now, UTC).date()
        start = (
            datetime.fromtimestamp(rows[0]["arrives_at"], UTC).date()
            if days == "all" and rows
            else today
            if days == "all"
            else today - timedelta(days=int(days) - 1)
        )
        selected = [
            row
            for row in rows
            if row["arrives_at"]
            >= datetime.combine(start, datetime.min.time(), UTC).timestamp()
        ]
        by_day: dict[str, list[dict[str, Any]]] = {}
        for row in selected:
            day = (
                datetime.fromtimestamp(row["arrives_at"], UTC)
                .date()
                .isoformat()
            )
            by_day.setdefault(day, []).append(row)
        series = []
        if rows:
            for offset in range((today - start).days + 1):
                day = (start + timedelta(days=offset)).isoformat()
                series.append({"date": day, **summarize(by_day.get(day, []))})
        LOGGER.info(
            "Company analytics read",
            extra={
                "event": "company.analytics.read",
                "data": {"scope": scope, "days": days, "rows": len(selected)},
            },
        )
        return {
            "server_time": now,
            "period": {
                "days": days,
                "from": start.isoformat(),
                "to": today.isoformat(),
                "timezone": "UTC",
            },
            "scope": {"type": scope, "id": scope_id},
            "status": data.status,
            "totals": summarize(rows),
            "period_totals": summarize(selected),
            "daily": series,
            "breakdowns": {
                key: breakdown(selected, key) for key in SCOPES[1:]
            },
            "ongoing": list(data.ongoing),
            "coverage": {
                "recorded_transports": len(data.history),
                "progress_completed": data.status["completed"],
                "v2_transports": sum(
                    row["market_model"] == "nhm_v2" for row in selected
                ),
                "unclassified_transports": sum(
                    row["market_model"] != "nhm_v2" for row in selected
                ),
            },
        }
