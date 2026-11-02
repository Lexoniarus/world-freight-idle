"""Shared multiplayer map traffic without weakening private player state."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap import (
    build_player_context,
)
from app.main import create_app
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)
from tests.transport_fixtures import add_transport

PASSWORD = "test-only-password-42"


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
