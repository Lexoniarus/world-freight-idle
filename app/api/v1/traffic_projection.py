"""Public traffic presentation without private transport economics."""

import logging
from dataclasses import asdict
from typing import Any

from app.domain.company_colors import player_color
from app.domain.read_ports import SharedTransport

LOGGER = logging.getLogger(__name__)


def project_traffic(
    rows: tuple[SharedTransport, ...], current_user_id: str
) -> list[dict[str, Any]]:
    """Project live traffic as public JSON and record its traceable counts."""
    traffic = [
        {
            "journey": {
                "distance_km": row.distance_km,
                "segments": [asdict(part) for part in row.segments],
            },
            "route_legs": [asdict(leg) for leg in row.route_legs],
            "id": row.id,
            "vehicle_id": row.vehicle_id,
            "model_id": row.model_id,
            "model_name": row.model_name,
            "username": row.username,
            "player_color": row.company_color or player_color(row.user_id),
            "is_own": row.user_id == current_user_id,
            "departed_at": row.departed_at,
            "arrives_at": row.arrives_at,
            "route_geojson": {
                "type": "LineString",
                "coordinates": [list(point) for point in row.coordinates],
            },
        }
        for row in rows
    ]
    LOGGER.info(
        "Shared map traffic projected",
        extra={
            "event": "map.traffic.read",
            "data": {
                "viewer_user_id": current_user_id,
                "active_transport_count": len(traffic),
                "visible_player_count": len({row.user_id for row in rows}),
            },
        },
    )
    return traffic
