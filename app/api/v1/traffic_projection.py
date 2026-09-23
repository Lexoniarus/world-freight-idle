"""Public traffic presentation without private transport economics."""

import colorsys
import hashlib
import logging
from typing import Any

from app.domain.read_ports import SharedTransport

LOGGER = logging.getLogger(__name__)


def player_color(user_id: str) -> str:
    """Derive a stable, saturated map color from a persistent user ID."""
    digest = hashlib.sha256(user_id.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65535
    red, green, blue = colorsys.hls_to_rgb(hue, 0.52, 0.70)
    channels = (round(red * 255), round(green * 255), round(blue * 255))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def project_traffic(
    rows: tuple[SharedTransport, ...], current_user_id: str
) -> list[dict[str, Any]]:
    """Project live traffic as public JSON and record its traceable counts."""
    traffic = [
        {
            "id": row.id,
            "vehicle_id": row.vehicle_id,
            "model_id": row.model_id,
            "model_name": row.model_name,
            "username": row.username,
            "player_color": player_color(row.user_id),
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
