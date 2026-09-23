"""Public multiplayer projection for active road traffic."""

from __future__ import annotations

import colorsys
import hashlib
import logging
import time
from typing import Any

from app.domain.read_ports import TrafficReader

LOGGER = logging.getLogger(__name__)


def player_color(user_id: str) -> str:
    """Derive a stable, saturated map color from a persistent user ID."""
    digest = hashlib.sha256(user_id.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65535
    red, green, blue = colorsys.hls_to_rgb(hue, 0.52, 0.70)
    channels = (round(red * 255), round(green * 255), round(blue * 255))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


class MultiplayerMapService:
    """Expose active transports without leaking private economy state."""

    def __init__(self, repository: TrafficReader) -> None:
        self.repository = repository

    def list_traffic(
        self,
        current_user_id: str,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        """Decorate minimal live-traffic rows with owner and color metadata."""
        active_at = time.time() if now is None else now
        rows = self.repository.list_active_transports(active_at)
        traffic = [
            {
                "id": row["id"],
                "vehicle_id": row["vehicle_id"],
                "model_id": row["model_id"],
                "model_name": row["model_name"],
                "username": row["username"],
                "player_color": player_color(row["user_id"]),
                "is_own": row["user_id"] == current_user_id,
                "departed_at": row["departed_at"],
                "arrives_at": row["arrives_at"],
                "route_geojson": row["route_geojson"],
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
                    "visible_player_count": len(
                        {row["user_id"] for row in rows}
                    ),
                },
            },
        )
        return traffic
