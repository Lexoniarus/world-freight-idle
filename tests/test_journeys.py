"""Energy timelines, boundary counterexamples and shared browser fixtures."""

import json
import math
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.domain.energy import EnergyKind, EnergyProfile, EnergyUnit
from app.domain.journeys import (
    JourneyPlan,
    JourneySegment,
    plan_journey,
    unmetered_journey,
)

PROFILE = EnergyProfile("diesel", "l", 100, 20, 10, 0.1)


def test_journey_reserve_stops_and_speed_limits():
    exact = plan_journey(450, 900, 90, PROFILE, 100, 10)
    assert exact.stop_count == 0
    assert exact.driving_seconds == exact.duration_seconds == 1800
    assert exact.progress_at(1800).energy_level == 10
    slower = plan_journey(450, 36000, 90, PROFILE, 100, 10)
    assert slower.driving_seconds == 3600
    multiple = plan_journey(1000, 36000, 100, PROFILE, 100, 1)
    assert multiple.stop_count == 2
    assert multiple.duration_seconds == 37200
    assert multiple.progress_at(37200).energy_level == 80
    for level in (0, 5, 10):
        origin = plan_journey(50, 1800, 100, PROFILE, level, 1)
        assert origin.segments[0].phase == "refuelling"
        assert origin.segments[0].start_km == 0
        assert origin.progress_at(599).energy_level == level
        assert origin.progress_at(600).energy_level == 100
    variants: tuple[tuple[EnergyKind, EnergyUnit, int], ...] = (
        ("gas", "kg", 25),
        ("electric", "kWh", 35),
    )
    for kind, unit, minutes in variants:
        profile = EnergyProfile(kind, unit, 100, 20, minutes, 0.1)
        plan = plan_journey(500, 18000, 100, profile, 100, 10)
        assert plan.duration_seconds == 1800 + minutes * 6
        assert plan.progress_at(1620).phase == (
            "charging" if kind == "electric" else "refuelling"
        )
    for index in range(6):
        values = [450, 900, 90, PROFILE, 100, 10]
        if index == 3:
            continue
        values[index] = math.nan
        with pytest.raises(ValueError):
            plan_journey(*values)
    with pytest.raises(ValueError):
        plan_journey(500, 18000, 100, PROFILE, 101, 1)
    with pytest.raises(ValueError, match="interval count"):
        plan_journey(5000000, 18000, 100, PROFILE, 100, 1)


def test_journey_progress_and_shared_timeline_boundaries():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/energy-timeline.json").read_text()
    )
    plan = plan_journey(**{**fixture["input"], "energy": PROFILE})
    assert json.loads(json.dumps(asdict(plan))) == fixture["journey"]
    for expected in fixture["samples"]:
        progress = plan.progress_at(expected["elapsed"])
        assert progress.phase == expected["phase"]
        assert progress.fraction == pytest.approx(expected["fraction"])
        assert progress.energy_level == pytest.approx(expected["energy"])
    with pytest.raises(ValueError):
        plan.progress_at(math.inf)
    legacy = unmetered_journey(400, 16)
    assert legacy.stop_count == 0
    assert legacy.driving_seconds == legacy.duration_seconds == 16
    assert legacy.progress_at(8).fraction == 0.5
    assert legacy.progress_at(17).energy_level is None
    with pytest.raises(ValueError):
        unmetered_journey(400, 0)


def test_journey_rejects_inconsistent_intervals_and_energy():
    plan = plan_journey(500, 18000, 100, PROFILE, 100, 1)
    drive, stop, final = plan.segments
    for changes in (
        {"phase": "missing"},
        {"ends_at": drive.starts_at},
        {"end_km": 0},
        {"start_km": -1},
        {"phase": "charging"},
    ):
        with pytest.raises(ValueError):
            replace(drive, **changes)
    for changes in (
        {"segments": ()},
        {"segments": list(plan.segments)},
        {"distance_km": 501},
        {"energy": None},
        {"segments": (replace(drive, starts_at=1), stop, final)},
        {"segments": (drive, replace(stop, start_energy=11), final)},
        {"segments": (replace(drive, start_energy=None), stop, final)},
        {"segments": (replace(drive, end_energy=None), stop, final)},
        {"segments": (replace(drive, end_energy=9), stop, final)},
        {"segments": (drive, replace(stop, end_energy=99), final)},
        {"segments": (drive, replace(stop, phase="charging"), final)},
        {"segments": (drive, stop), "distance_km": 450},
    ):
        with pytest.raises(ValueError):
            replace(plan, **changes)
    below_reserve = JourneySegment("driving", 0, 1, 0, 460, 100, 8)
    with pytest.raises(ValueError, match="reserve"):
        JourneyPlan(460, PROFILE, (below_reserve,))
    unmetered = unmetered_journey(400, 16)
    with pytest.raises(ValueError, match="Unmetered"):
        replace(
            unmetered,
            segments=(replace(unmetered.segments[0], start_energy=100),),
        )
