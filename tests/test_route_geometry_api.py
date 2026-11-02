"""Compact polling retains authoritative facts without hydrating geometry."""

from dataclasses import replace

import pytest
from fastapi import HTTPException

from app.api.v1.runtime import (
    parse_route_reference,
    route_reference,
)
from app.bootstrap import build_runtime_reader
from app.domain.routes import DispatchRoutePlan


@pytest.mark.parametrize(
    "value",
    [
        "",
        "x" * 1025,
        "%%%",
        "WzJd",
        "WzEsIiIsInQiXQ",
        "W3RydWUsImEiLCJiIl0",
        "e30",
        "_w",
    ],
)
def test_route_references_reject_malformed_or_unsupported_identifiers(value):
    assert parse_route_reference(route_reference("owner", "trip")) == (
        "owner",
        "trip",
    )
    with pytest.raises(HTTPException):
        parse_route_reference(value)


def test_runtime_geometry_preserves_shared_and_distinct_leg_boundaries(
    active_trip, synthetic_runtime, synthetic_game
):
    reader = build_runtime_reader(synthetic_runtime)
    base = active_trip.route
    for same in (True, False):
        start = replace(active_trip.origin, facility_uid="departure")
        approach = replace(
            base,
            coordinates=((0, 0), base.coordinates[0] if same else (0.5, 0.5)),
        )
        plan = DispatchRoutePlan(
            start, active_trip.origin, active_trip.destination, base, approach
        )
        from app.domain.journeys import unmetered_journey

        updated = replace(
            active_trip,
            dispatch_route=plan,
            route=plan.total_route,
            journey=unmetered_journey(plan.total_route.distance_km, 20),
        )
        with synthetic_runtime.database.connect() as db:
            db.execute("DELETE FROM transports")
        synthetic_game.state_repository.save_transport(updated)
        shape = reader.geometry("test-owner", active_trip.id)
        assert shape.coordinates == plan.total_route.coordinates
        assert shape.legs[1].start_index == (1 if same else 2)
        assert (
            shape.coordinates[
                shape.legs[1].start_index : shape.legs[1].end_index
            ]
            == base.coordinates
        )
        assert (
            reader.read("test-owner").transports[0].approach_distance_km
            == base.distance_km
        )
    single = replace(
        active_trip,
        dispatch_route=DispatchRoutePlan(
            active_trip.origin,
            active_trip.origin,
            active_trip.destination,
            base,
        ),
    )
    with synthetic_runtime.database.connect() as db:
        db.execute("DELETE FROM transports")
    synthetic_game.state_repository.save_transport(single)
    assert len(reader.geometry("test-owner", active_trip.id).legs) == 1
