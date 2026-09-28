"""Compact polling retains authoritative facts without hydrating geometry."""

import json
import time
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_current_user, get_vehicle_catalogue
from app.api.v1.runtime import parse_route_reference, route_reference
from app.bootstrap import build_runtime_reader, build_runtime_view
from app.domain.errors import PersistenceError
from app.domain.routes import DispatchRoutePlan
from app.main import create_app
from app.repositories.runtime_views import (
    load_runtime_traffic,
    load_runtime_transport,
    validate_runtime_envelope,
)
from app.repositories.state_snapshots import (
    dataclass_document,
    encode_snapshot,
)
from tests.test_api import FakeGame, make_settings, make_static_files


@pytest.fixture
def active_trip(game):
    now = time.time()
    trip = replace(FakeGame(game).trip, departed_at=now, arrives_at=now + 20)
    with game.unit_of_work.transaction():
        vehicle = game.get_vehicle(trip.vehicle_id)
        vehicle.start_trip()
        game.state_repository.save_vehicle(vehicle)
        game.state_repository.save_transport(trip)
    return trip


def test_runtime_reads_exclude_geometry_and_keep_private_energy(
    active_trip,
    runtime,
    tmp_path,
):
    reader = build_runtime_reader(runtime)
    service = build_runtime_view(runtime, "test-owner")
    with patch(
        "app.repositories.runtime_views.load_transport_record",
        side_effect=AssertionError("Geometry hydrated during polling"),
    ):
        view = service.read()
        public = reader.traffic(active_trip.departed_at)
    assert view.state.transports[0].id == active_trip.id
    assert public[0].coordinates == ()
    assert public[0].distance_km == active_trip.route.distance_km
    assert view.state.player.cash == 175000
    with pytest.raises(PersistenceError):
        reader.read("missing-owner")
    assert reader.visible(
        "test-owner", active_trip.id, "other", active_trip.departed_at
    )
    assert not reader.visible(
        "test-owner", active_trip.id, "other", active_trip.arrives_at
    )
    assert reader.visible(
        "test-owner", active_trip.id, "test-owner", active_trip.arrives_at
    )
    assert not reader.visible("other", active_trip.id, "test-owner", 0)
    assert (
        reader.geometry("test-owner", active_trip.id).coordinates
        == active_trip.route.coordinates
    )
    with pytest.raises(KeyError):
        reader.geometry("other", active_trip.id)
    assert dataclass_document(active_trip)["route"] is active_trip.route
    with pytest.raises(TypeError):
        dataclass_document(type(active_trip))
    with pytest.raises(PersistenceError):
        encode_snapshot("transport", object())

    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    app.state.game = runtime
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-owner"}
    app.dependency_overrides[get_vehicle_catalogue] = lambda: runtime.catalogue
    client = TestClient(app)
    summary = client.get("/api/v1/runtime")
    assert summary.status_code == 200
    body = summary.json()
    assert '"coordinates":[' not in summary.text
    assert "route_geojson" not in summary.text
    assert body["transports"][0]["payout_eur"] == active_trip.payout_eur
    reference = body["transports"][0]["route_ref"]
    response = client.get("/api/v1/map/routes/" + reference)
    assert response.status_code == 200
    assert response.json()["coordinates"] == [
        list(p) for p in active_trip.route.coordinates
    ]
    assert response.json()["legs"] == []
    with patch.object(
        type(reader),
        "geometry",
        side_effect=AssertionError("304 decoded route"),
    ):
        assert (
            client.get(
                "/api/v1/map/routes/" + reference,
                headers={"If-None-Match": response.headers["etag"]},
            ).status_code
            == 304
        )
    traffic = client.get("/api/v1/map/traffic?representation=summary")
    assert traffic.status_code == 200
    assert traffic.json()["transports"][0]["route_ref"] == reference
    for private in ("coordinates", "payout_eur", "energy", "contract"):
        assert private not in traffic.text
    assert (
        client.get("/api/v1/map/traffic?representation=unknown").status_code
        == 422
    )
    assert client.get("/api/v1/map/routes/invalid").status_code == 404
    with patch.object(
        type(reader), "geometry", side_effect=KeyError("disappeared")
    ):
        assert client.get("/api/v1/map/routes/" + reference).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: {"id": "other"}
    with patch(
        "app.api.v1.runtime.time.time", return_value=active_trip.arrives_at
    ):
        assert (
            client.get(
                "/api/v1/map/routes/" + reference,
                headers={"If-None-Match": response.headers["etag"]},
            ).status_code
            == 404
        )
    app.dependency_overrides.pop(get_current_user)
    app.state.auth = SimpleNamespace(
        accounts=SimpleNamespace(session_user=lambda _: None)
    )
    assert client.get("/api/v1/runtime").status_code == 401
    assert client.get("/api/v1/map/routes/" + reference).status_code == 401


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
    active_trip, runtime, game
):
    reader = build_runtime_reader(runtime)
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
        with runtime.database.connect() as db:
            db.execute("DELETE FROM transports")
        game.state_repository.save_transport(updated)
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
    with runtime.database.connect() as db:
        db.execute("DELETE FROM transports")
    game.state_repository.save_transport(single)
    assert len(reader.geometry("test-owner", active_trip.id).legs) == 1


def test_runtime_projection_rejects_corrupt_scalars_without_reading_history(
    active_trip, runtime
):
    reader = build_runtime_reader(runtime)
    trip = reader.read("test-owner").transports[0]
    for changes in (
        {"id": ""},
        {"distance_km": -1},
        {"distance_km": 99},
        {"payout_eur": True},
        {"arrives_at": trip.departed_at},
        {"origin": trip.destination},
        {"approach_distance_km": 100},
    ):
        with pytest.raises(ValueError):
            replace(trip, **changes)
    with pytest.raises(ValueError):
        validate_runtime_envelope({"version": True, "kind": "transport"})
    with pytest.raises(PersistenceError):
        load_runtime_traffic(
            {"version": 2, "kind": "transport", "journey": "{}"}
        )
    with pytest.raises(PersistenceError):
        load_runtime_transport({"version": 2, "kind": "transport"})
    with runtime.database.connect() as db:
        raw = db.execute(
            "SELECT transport_snapshot FROM transports"
        ).fetchone()[0]
        value = json.loads(raw)
        for field, invalid in (
            ("vehicle_id", "different"),
            ("id", "different"),
            ("journey", {}),
        ):
            document = json.loads(raw)
            document["data"][field] = invalid
            db.execute(
                "UPDATE transports SET transport_snapshot=?",
                (json.dumps(document),),
            )
            with pytest.raises(PersistenceError):
                reader.read("test-owner")
        db.execute(
            "UPDATE transports SET transport_snapshot=?", (json.dumps(value),)
        )
