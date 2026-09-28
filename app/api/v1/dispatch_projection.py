"""HTTP projection of historical departure and ordered route sections."""

from dataclasses import asdict
from typing import Any

from app.api.v1.location_projection import project_location
from app.domain.routes import DispatchRoutePlan, RouteSnapshot
from app.domain.world import FacilityLocationSnapshot


def project_dispatch_route(
    plan: DispatchRoutePlan | None,
    origin: FacilityLocationSnapshot,
    route: RouteSnapshot,
) -> dict[str, Any]:
    """Expose departure and single-leg defaults for historical trips."""
    return {
        "start": project_location(plan.start if plan else origin),
        "approach_distance_km": (
            plan.approach.distance_km if plan and plan.approach else 0.0
        ),
        "delivery_distance_km": (
            plan.delivery.distance_km if plan else route.distance_km
        ),
        "route_legs": [asdict(leg) for leg in plan.legs] if plan else [],
    }
