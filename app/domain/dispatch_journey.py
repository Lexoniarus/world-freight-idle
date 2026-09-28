"""Pure composition of energy-continuous approach and delivery timelines."""

from dataclasses import replace

from app.domain.energy import EnergyProfile
from app.domain.journeys import JourneyPlan, JourneySegment, plan_journey
from app.domain.routes import DispatchRoutePlan


def plan_dispatch_journey(
    route: DispatchRoutePlan,
    top_speed_kmh: float,
    energy: EnergyProfile,
    start_level: float,
    time_scale: float,
) -> JourneyPlan:
    """Plan each road section with its own speed and carried energy level."""
    roads = (
        (route.delivery,)
        if route.approach is None
        else (route.approach, route.delivery)
    )
    parts: list[JourneySegment] = []
    seconds, distance, level = 0.0, 0.0, start_level
    for road in roads:
        section = plan_journey(
            road.distance_km,
            road.duration_seconds,
            top_speed_kmh,
            energy,
            level,
            time_scale,
        )
        parts.extend(
            replace(
                part,
                starts_at=seconds + part.starts_at,
                ends_at=seconds + part.ends_at,
                start_km=distance + part.start_km,
                end_km=distance + part.end_km,
            )
            for part in section.segments
        )
        seconds = parts[-1].ends_at
        distance = parts[-1].end_km
        end_level = parts[-1].end_energy
        assert end_level is not None
        level = end_level
    return JourneyPlan(distance, energy, tuple(parts))
