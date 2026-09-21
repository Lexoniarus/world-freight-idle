"""Shared multiplayer map traffic without weakening private player state."""

from __future__ import annotations

import logging
import re

from fastapi.testclient import TestClient

from app.bootstrap import (
    build_multiplayer_map_service,
    build_player_service,
)
from app.main import create_app
from app.repositories.accounts import AccountRepository
from app.repositories.multiplayer_map import MultiplayerMapRepository
from app.services.multiplayer_map import player_color
from tests.test_api import make_settings, make_static_files

PASSWORD = "test-only-password-42"
ROUTE = {
    "type": "LineString",
    "coordinates": [[13.3, 52.5], [13.5, 52.6]],
}


def active_trip(trip_id: str, vehicle_id: str, now: float) -> dict:
    """Create a persisted trip fixture with intentionally private fields."""
    return {
        "id": trip_id,
        "vehicle_id": vehicle_id,
        "departed_at": now - 10,
        "arrives_at": now + 100,
        "route_geojson": ROUTE,
        "payout_eur": 1234,
        "operating_cost_eur": 321,
        "profit_eur": 913,
        "contract": {"cargo": "Private cargo detail"},
    }


def test_multiplayer_map_projects_shared_active_traffic_without_private_economy(
    game,
    caplog,
):
    accounts = AccountRepository(game.store)
    alice = accounts.create_user("Alice", "unused")
    bob = accounts.create_user("Bob", "unused")
    alice_game = build_player_service(game, alice["id"])
    bob_game = build_player_service(game, bob["id"])
    now = game.now()

    alice_vehicle = alice_game.store.get_json("vehicles")[0]
    bob_vehicle = bob_game.store.get_json("vehicles")[0]
    bob_vehicle["model_id"] = "daf_xg_plus_480"
    bob_vehicle["name"] = "DAF XG+ 480 MX-13"
    bob_game.store.set_json("vehicles", [bob_vehicle])
    alice_game.store.set_json(
        "active_trips",
        [active_trip("alice-trip", alice_vehicle["id"], now)],
    )
    bob_game.store.set_json(
        "active_trips",
        [
            active_trip("bob-trip", bob_vehicle["id"], now),
            {
                **active_trip("expired", bob_vehicle["id"], now),
                "arrives_at": now - 1,
            },
        ],
    )

    repository = MultiplayerMapRepository(game.store)
    rows = repository.list_active_transports(now)
    assert [row["id"] for row in rows] == ["alice-trip", "bob-trip"]
    assert set(rows[0]) == {
        "user_id",
        "username",
        "id",
        "vehicle_id",
        "model_id",
        "model_name",
        "departed_at",
        "arrives_at",
        "route_geojson",
    }

    service = build_multiplayer_map_service(game)
    with caplog.at_level(logging.INFO):
        traffic = service.list_traffic(alice["id"], now=now)

    assert [item["id"] for item in traffic] == ["alice-trip", "bob-trip"]
    own = next(item for item in traffic if item["id"] == "alice-trip")
    other = next(item for item in traffic if item["id"] == "bob-trip")
    assert own["is_own"] is True
    assert other["is_own"] is False
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
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        client.headers["X-Freight-Request"] = "1"
        assert client.get("/api/v1/map/traffic").status_code == 401

        alice_response = client.post(
            "/api/v1/auth/register",
            json={"username": "Alice", "password": PASSWORD},
        )
        alice = alice_response.json()
        alice_game = build_player_service(app.state.game, alice["id"])
        now = alice_game.now()
        vehicle = alice_game.store.get_json("vehicles")[0]
        alice_game.store.set_json(
            "active_trips",
            [active_trip("alice-live", vehicle["id"], now)],
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
