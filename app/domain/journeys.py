"""Deterministic distance, energy and pause timelines without clocks or IO."""

from dataclasses import dataclass
from math import isclose
from typing import Literal

from app.domain.energy import EnergyProfile
from app.domain.validation import require_finite

JourneyPhase = Literal["driving", "refuelling", "charging", "arrived"]


@dataclass(frozen=True, slots=True)
class JourneySegment:
    """One driving or stationary interval, relative to departure."""

    phase: Literal["driving", "refuelling", "charging"]
    starts_at: float
    ends_at: float
    start_km: float
    end_km: float
    start_energy: float | None
    end_energy: float | None

    def __post_init__(self) -> None:
        """Require ordered finite coordinates and physically shaped phases."""
        for value in (
            self.starts_at,
            self.ends_at,
            self.start_km,
            self.end_km,
        ):
            require_finite(value, "Journey boundary")
        if self.ends_at <= self.starts_at or self.end_km < self.start_km:
            raise ValueError("Journey interval must advance time.")
        if self.phase == "driving":
            if self.end_km == self.start_km:
                raise ValueError("Driving interval must advance distance.")
        elif self.phase in {"refuelling", "charging"}:
            if self.end_km != self.start_km:
                raise ValueError("Energy stop must remain stationary.")
        else:
            raise ValueError("Unknown journey phase.")


@dataclass(frozen=True, slots=True)
class JourneyProgress:
    """Calculated state at one caller-supplied point in time."""

    phase: JourneyPhase
    distance_km: float
    fraction: float
    energy_level: float | None
    phase_remaining_seconds: float


@dataclass(frozen=True, slots=True)
class JourneyPlan:
    """Historical itinerary; unmetered plans preserve pre-energy trips."""

    distance_km: float
    energy: EnergyProfile | None
    segments: tuple[JourneySegment, ...]

    def __post_init__(self) -> None:
        """Reject discontinuities and energy changes outside physical rules."""
        require_finite(self.distance_km, "Journey distance", 0.000001)
        if not isinstance(self.segments, tuple) or not self.segments:
            raise ValueError("Journey requires immutable intervals.")
        seconds, distance = 0.0, 0.0
        previous_level = self.segments[0].start_energy
        for segment in self.segments:
            if segment.starts_at != seconds or segment.start_km != distance:
                raise ValueError("Journey intervals are not contiguous.")
            if segment.start_energy != previous_level:
                raise ValueError("Journey energy is not continuous.")
            self._validate_segment_energy(segment)
            seconds, distance = segment.ends_at, segment.end_km
            previous_level = segment.end_energy
        if distance != self.distance_km:
            raise ValueError("Journey does not reach its destination.")
        if self.segments[-1].phase != "driving":
            raise ValueError("Journey cannot end with an energy stop.")

    def _validate_segment_energy(self, segment: JourneySegment) -> None:
        """Check consumption and refill conservation for one interval."""
        if self.energy is None:
            if (
                len(self.segments) != 1
                or segment.phase != "driving"
                or segment.start_energy is not None
                or segment.end_energy is not None
            ):
                raise ValueError("Unmetered journey cannot simulate energy.")
            return
        if segment.start_energy is None or segment.end_energy is None:
            raise ValueError("Metered journey requires energy levels.")
        self.energy.validate_level(segment.start_energy)
        self.energy.validate_level(segment.end_energy)
        if segment.phase == "driving":
            expected = segment.start_energy - self.energy.consumption_for(
                segment.end_km - segment.start_km
            )
            if not isclose(expected, segment.end_energy, abs_tol=1e-9):
                raise ValueError("Journey consumption differs.")
            reserve = self.energy.capacity * self.energy.reserve_fraction
            if segment.end_energy < reserve - 1e-9:
                raise ValueError("Journey consumes its energy reserve.")
        else:
            phase = (
                "charging" if self.energy.kind == "electric" else "refuelling"
            )
            if (
                segment.phase != phase
                or segment.end_energy != self.energy.capacity
                or segment.start_energy >= self.energy.capacity
            ):
                raise ValueError("Journey refill differs from its profile.")

    @property
    def duration_seconds(self) -> float:
        """Return scaled driving time plus all pauses."""
        return self.segments[-1].ends_at

    @property
    def driving_seconds(self) -> float:
        """Return scaled time spent moving."""
        return sum(
            part.ends_at - part.starts_at
            for part in self.segments
            if part.phase == "driving"
        )

    @property
    def stop_count(self) -> int:
        """Count refuelling and charging intervals."""
        return sum(part.phase != "driving" for part in self.segments)

    def progress_at(self, elapsed_seconds: float) -> JourneyProgress:
        """Interpolate movement; refill only at the exact end of a stop."""
        require_finite(elapsed_seconds, "Elapsed time", -1e300)
        elapsed = max(0.0, elapsed_seconds)
        for part in self.segments:
            if elapsed < part.ends_at:
                ratio = (elapsed - part.starts_at) / (
                    part.ends_at - part.starts_at
                )
                distance = (
                    part.start_km + (part.end_km - part.start_km) * ratio
                )
                level = part.start_energy
                if (
                    part.phase == "driving"
                    and level is not None
                    and part.end_energy is not None
                ):
                    level += (part.end_energy - level) * ratio
                return JourneyProgress(
                    part.phase,
                    distance,
                    distance / self.distance_km,
                    level,
                    part.ends_at - elapsed,
                )
        return JourneyProgress(
            "arrived",
            self.distance_km,
            1.0,
            self.segments[-1].end_energy,
            0.0,
        )


def plan_journey(
    distance_km: float,
    provider_seconds: float,
    top_speed_kmh: float,
    energy: EnergyProfile,
    start_level: float,
    time_scale: float,
) -> JourneyPlan:
    """Plan constant consumption and automatic stops along a saved route."""
    for value in (distance_km, provider_seconds, top_speed_kmh, time_scale):
        require_finite(value, "Journey measurement", 0.000001)
    energy.validate_level(start_level)
    driving_seconds = (
        max(provider_seconds, distance_km / top_speed_kmh * 3600) / time_scale
    )
    seconds_per_km = driving_seconds / distance_km
    stop_seconds = energy.stop_minutes * 60 / time_scale
    reserve = energy.capacity * energy.reserve_fraction
    per_km = energy.consumption_per_100km / 100
    parts: list[JourneySegment] = []
    distance, seconds, level = 0.0, 0.0, start_level
    while distance < distance_km:
        if len(parts) >= 20001:
            raise ValueError("Journey exceeds supported interval count.")
        remaining = distance_km - distance
        reachable = max(0.0, (level - reserve) / per_km)
        if reachable > 1e-9:
            final_leg = remaining <= reachable or isclose(
                remaining, reachable, rel_tol=1e-12, abs_tol=1e-9
            )
            end_km = distance_km if final_leg else distance + reachable
            used = energy.consumption_for(end_km - distance)
            end_level = max(reserve, level - used)
            ends_at = seconds + (end_km - distance) * seconds_per_km
            parts.append(
                JourneySegment(
                    "driving",
                    seconds,
                    ends_at,
                    distance,
                    end_km,
                    level,
                    end_level,
                )
            )
            distance, seconds, level = end_km, ends_at, end_level
        if distance < distance_km:
            parts.append(
                JourneySegment(
                    "charging" if energy.kind == "electric" else "refuelling",
                    seconds,
                    seconds + stop_seconds,
                    distance,
                    distance,
                    level,
                    energy.capacity,
                )
            )
            seconds += stop_seconds
            level = energy.capacity
    return JourneyPlan(distance_km, energy, tuple(parts))


def unmetered_journey(distance_km: float, duration: float) -> JourneyPlan:
    """Preserve historical travel timing without new stops or energy use."""
    return JourneyPlan(
        distance_km,
        None,
        (JourneySegment("driving", 0, duration, 0, distance_km, None, None),),
    )
