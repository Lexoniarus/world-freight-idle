"""Restore historical transport documents independently of HTTP formats."""

from typing import Any

from app.domain.economics import CostBreakdown, EnergyPurchase
from app.domain.energy import EnergyProfile
from app.domain.journeys import JourneyPlan, JourneySegment
from app.domain.routes import DispatchRoutePlan, RouteSnapshot
from app.domain.transports import ActiveTransport
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
            "cost_breakdown": load_cost_breakdown(value.get("cost_breakdown")),
            "dispatch_route": load_dispatch_route(value.get("dispatch_route")),
            "contract": load_historical_contract(value["contract"]),
            "origin": load_location(value["origin"]),
            "destination": load_location(value["destination"]),
            "route": load_route(route),
            "status": value["status"],
            "settled_at": value["settled_at"],
        }
    )


def load_journey(value: dict[str, Any]) -> JourneyPlan:
    """Decode the single versioned itinerary representation."""
    return JourneyPlan(
        **{
            **value,
            "energy": EnergyProfile(**value["energy"])
            if value["energy"] is not None
            else None,
            "segments": tuple(
                JourneySegment(**part) for part in value["segments"]
            ),
        }
    )


def load_route(value: dict[str, Any]) -> RouteSnapshot:
    """Restore one immutable provider route without another routing call."""
    return RouteSnapshot(
        **{
            **value,
            "coordinates": tuple(tuple(p) for p in value["coordinates"]),
        }
    )


def load_dispatch_route(
    value: dict[str, Any] | None,
) -> DispatchRoutePlan | None:
    """Read optional plans without changing historical trips."""
    if value is None:
        return None
    return DispatchRoutePlan(
        **{
            **value,
            "start": load_location(value["start"]),
            "pickup": load_location(value["pickup"]),
            "destination": load_location(value["destination"]),
            "delivery": load_route(value["delivery"]),
            "approach": (
                load_route(value["approach"])
                if value["approach"] is not None
                else None
            ),
        }
    )


def load_cost_breakdown(value: dict[str, Any] | None) -> CostBreakdown | None:
    """Decode optional historical purchase facts without price lookup."""
    if value is None:
        return None
    return CostBreakdown(
        **{
            **value,
            "purchases": tuple(
                EnergyPurchase(**part) for part in value["purchases"]
            ),
        }
    )
