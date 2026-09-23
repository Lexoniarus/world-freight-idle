"""Restore historical transport documents independently of HTTP formats."""

from typing import Any

from app.domain.energy import EnergyProfile
from app.domain.journeys import JourneyPlan, JourneySegment
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.repositories.snapshot_mapping import (
    load_historical_contract,
    load_location,
)


def load_transport(value: dict[str, Any]) -> ActiveTransport:
    """Restore canonical dispatch facts without legacy hydration."""
    route = value["route"]
    return ActiveTransport(
        **{
            **value,
            "journey": load_journey(value["journey"]),
            "contract": load_historical_contract(value["contract"]),
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


def load_journey(value: dict[str, Any]) -> JourneyPlan:
    """Decode the single versioned itinerary representation."""
    return JourneyPlan(
        distance_km=value["distance_km"],
        energy=EnergyProfile(**value["energy"])
        if value["energy"] is not None
        else None,
        segments=tuple(JourneySegment(**part) for part in value["segments"]),
    )
