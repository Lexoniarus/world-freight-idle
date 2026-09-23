"""Restore historical transport documents independently of HTTP formats."""

from typing import Any

from app.domain.transports import ActiveTransport, RouteSnapshot
from app.repositories.snapshot_mapping import load_location, load_offer


def load_transport(value: dict[str, Any]) -> ActiveTransport:
    """Restore canonical dispatch facts without legacy hydration."""
    route = value["route"]
    return ActiveTransport(
        **{
            **value,
            "contract": load_offer(value["contract"]),
            "origin": load_location(value["origin"]),
            "destination": load_location(value["destination"]),
            "route": RouteSnapshot(
                **{
                    **route,
                    "coordinates": tuple(
                        tuple(point) for point in route["coordinates"]
                    ),
                }
            ),
            "status": value["status"],
            "settled_at": value["settled_at"],
        }
    )
