"""Project typed analytics results to the existing HTTP contract."""

from dataclasses import asdict
from typing import Any

from app.domain.analytics import AnalyticsResult


def project_analytics(result: AnalyticsResult) -> dict[str, Any]:
    """Preserve field names, flattened metrics and historical nulls."""
    return {
        "server_time": result.server_time,
        "period": {
            "days": result.days,
            "from": result.start_date,
            "to": result.end_date,
            "timezone": "UTC",
        },
        "scope": {"type": result.scope, "id": result.scope_id},
        "status": asdict(result.status),
        "totals": asdict(result.totals),
        "period_totals": asdict(result.period_totals),
        "daily": [
            {"date": day.date, **asdict(day.summary)} for day in result.daily
        ],
        "breakdowns": {
            dimension: [
                {"id": group.id, "label": group.label, **asdict(group.summary)}
                for group in groups
            ]
            for dimension, groups in result.breakdowns
        },
        "ongoing": [
            {**asdict(row), "vehicle_label": label}
            for row, label in result.ongoing
        ],
        "coverage": {
            "recorded_transports": result.recorded_transports,
            "progress_completed": result.status.completed,
            "v2_transports": result.v2_transports,
            "unclassified_transports": result.unclassified_transports,
        },
    }
