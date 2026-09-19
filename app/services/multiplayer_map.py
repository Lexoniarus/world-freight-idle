"""Public multiplayer projection for active road traffic."""

from __future__ import annotations

import colorsys
import hashlib
import time
from typing import Any

from app.repositories.multiplayer_map import MultiplayerMapRepository


def player_color(user_id: str) -> str:
    """Derive a stable, saturated map color from a persistent user ID."""
    digest = hashlib.sha256(user_id.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65535
    red, green, blue = colorsys.hls_to_rgb(hue, 0.52, 0.70)
    channels = (round(red * 255), round(green * 255), round(blue * 255))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


class MultiplayerMapService:
    """Expose active transports without leaking private economy state."""

    def __init__(self, repository: MultiplayerMapRepository) -> None:
        self.repository = repository

    def list_traffic(
        self,
        current_user_id: str,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        """Project all live transports into a minimal shared map payload."""
        active_at = time.time() if now is None else now
        traffic: list[dict[str, Any]] = []
        for state in self.repository.list_player_states():
            vehicles = {
                vehicle.get("id"): vehicle
                for vehicle in state["vehicles"]
                if vehicle.get("id")
            }
            color = player_color(state["user_id"])
            for trip in state["active_trips"]:
                arrives_at = trip.get("arrives_at")
                departed_at = trip.get("departed_at")
                trip_id = trip.get("id")
                vehicle_id = trip.get("vehicle_id")
                route = trip.get("route_geojson")
                vehicle = vehicles.get(vehicle_id)
                if (
                    not trip_id
                    or not vehicle_id
                    or vehicle is None
                    or route is None
                    or not isinstance(arrives_at, (int, float))
                    or not isinstance(departed_at, (int, float))
                    or arrives_at <= active_at
                ):
                    continue
                traffic.append(
                    {
                        "id": trip_id,
                        "vehicle_id": vehicle_id,
                        "model_id": vehicle.get("model_id", ""),
                        "username": state["username"],
                        "player_color": color,
                        "is_own": state["user_id"] == current_user_id,
                        "departed_at": departed_at,
                        "arrives_at": arrives_at,
                        "route_geojson": route,
                    }
                )
        traffic.sort(key=lambda item: (item["departed_at"], item["id"]))
        return traffic
