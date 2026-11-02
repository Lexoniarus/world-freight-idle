"""Shared multiplayer map traffic without weakening private player state."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict

from fastapi.testclient import TestClient

from app.api.v1.traffic_projection import player_color, project_traffic
from app.bootstrap import (
    build_player_context,
    build_preferences,
    build_traffic_reader,
)
from app.main import create_app
from app.repositories.accounts import AccountRepository
from app.repositories.relational_traffic import SqliteTrafficReader
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)
from tests.transport_fixtures import add_transport

PASSWORD = "test-only-password-42"
ROUTE = {
    "type": "LineString",
    "coordinates": [[13, 52], [9, 53]],
}


def test_multiplayer_map_projects_active_traffic_without_private_economy(
    database,
    synthetic_runtime,
    synthetic_game,
    caplog,
):
    accounts = AccountRepository(database)
    alice = accounts.create_user("Alice", "unused")
    bob = accounts.create_user("Bob", "unused")
    alice_context = build_player_context(synthetic_runtime, alice["id"])
    bob_context = build_player_context(synthetic_runtime, bob["id"])
    alice_game = alice_context.game
    bob_game = bob_context.game
    now = synthetic_game.now()

    bob_vehicle = bob_context.state_repository.list_vehicles()[0]
    model = next(
        item
        for item in synthetic_runtime.catalogue.list_models()
        if item.id == "daf_xg_plus_480"
    )
    bob_vehicle.apply_model(model)
    bob_context.state_repository.save_vehicle(bob_vehicle)
    for service, context, identity in (
        (alice_game, alice_context, "alice-trip"),
        (bob_game, bob_context, "bob-trip"),
    ):
        add_transport(
            service,
            departed_at=now - 10,
            arrives_at=now + 100,
            transport_id=identity,
            context=context,
        )
    build_preferences(synthetic_runtime).update(bob["id"], "#e45756")
    repository = SqliteTrafficReader(database)
    assert repository.list_active_transports(now + 200) == ()
    rows = repository.list_active_transports(now)
    assert {row.id for row in rows} == {"alice-trip", "bob-trip"}
    assert set(asdict(rows[0])) == {
        "user_id",
        "username",
        "id",
        "vehicle_id",
        "model_id",
        "model_name",
        "departed_at",
        "arrives_at",
        "coordinates",
        "distance_km",
        "segments",
        "route_legs",
        "company_color",
    }
    assert rows[0].route_legs == ()
    assert set(asdict(rows[0].segments[0])) == {
        "phase",
        "starts_at",
        "ends_at",
        "start_km",
        "end_km",
    }

    reader = build_traffic_reader(synthetic_runtime)
    with caplog.at_level(logging.INFO):
        traffic = project_traffic(
            reader.list_active_transports(now), alice["id"]
        )
        assert project_traffic((), alice["id"]) == []

    assert {item["id"] for item in traffic} == {"alice-trip", "bob-trip"}
    own = next(item for item in traffic if item["id"] == "alice-trip")
    other = next(item for item in traffic if item["id"] == "bob-trip")
    assert own["is_own"] is True
    assert other["is_own"] is False
    assert other["player_color"] == "#e45756"
    assert own["username"] == "Alice"
    assert other["username"] == "Bob"
    assert own["model_id"] == "iveco_sway_500"
    assert other["model_id"] == "daf_xg_plus_480"
    assert own["model_name"] != other["model_name"]
    assert own["route_geojson"] == ROUTE
    assert other["route_geojson"] == ROUTE
    assert own["player_color"] != other["player_color"]
    assert re.fullmatch(r"#[0-9a-f]{6}", own["player_color"])
    assert {
        "payout_eur",
        "operating_cost_eur",
        "profit_eur",
        "contract",
    }.isdisjoint(own)
    assert any(
        record.msg == "Shared map traffic projected"
        for record in caplog.records
    )


def test_player_color_is_stable_and_changes_between_users():
    assert player_color("alice-id") == player_color("alice-id")
    assert player_color("alice-id") != player_color("bob-id")
    assert re.fullmatch(r"#[0-9a-f]{6}", player_color("alice-id"))


def test_multiplayer_map_endpoint_requires_login_and_shares_other_players(
    tmp_path,
):
    create_minimal_static_files(tmp_path)
    app = create_app(build_synthetic_application_settings(tmp_path))
    with TestClient(app) as client:
        client.headers["X-Freight-Request"] = "1"
        assert client.get("/api/v1/map/traffic").status_code == 401

        alice_response = client.post(
            "/api/v1/auth/register",
            json={"username": "Alice", "password": PASSWORD},
        )
        alice = alice_response.json()
        alice_context = build_player_context(
            app.state.game_runtime,
            alice["id"],
        )
        alice_game = alice_context.game
        now = alice_game.now()
        add_transport(
            alice_game,
            departed_at=now - 10,
            arrives_at=now + 100,
            transport_id="alice-live",
            context=alice_context,
        )

        bob_response = client.post(
            "/api/v1/auth/register",
            json={"username": "Bob", "password": PASSWORD},
        )
        assert bob_response.status_code == 201
        traffic = client.get("/api/v1/map/traffic").json()["transports"]
        alice_public = next(
            item for item in traffic if item["id"] == "alice-live"
        )
        assert alice_public["username"] == "Alice"
        assert alice_public["is_own"] is False
