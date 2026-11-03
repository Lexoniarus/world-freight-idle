"""Authentication, session security and account-isolation API tests."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.accounts import AccountRepository
from app.services.auth import SESSION_COOKIE, AuthService, PasswordHasher
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)
from tests.support.routing_runtime import (
    install_fake_routing_providers,
    prepare_client_market,
)

PASSWORD = "test-only-password-42"


@pytest.fixture
def auth_api(tmp_path):
    """Provide an isolated same-origin API client with fake routing."""
    create_minimal_static_files(tmp_path)
    app = create_app(build_synthetic_application_settings(tmp_path))
    with TestClient(app) as client:
        install_fake_routing_providers(app.state.game_runtime)
        yield app, client


def _register(client, username):
    """Register one synthetic account through the public API."""
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )


def test_password_hashes_are_salted_and_verified():
    hasher = PasswordHasher()
    encoded = hasher.hash_password(PASSWORD)
    assert PASSWORD not in encoded
    assert encoded != hasher.hash_password(PASSWORD)
    assert hasher.verify_password(PASSWORD, encoded)
    assert not hasher.verify_password("wrong", encoded)


def test_auth_sessions_expire_revoke_and_throttle(database):
    accounts = AccountRepository(database)
    auth = AuthService(accounts, PasswordHasher())
    user = auth.register("FreightOne", PASSWORD)
    with pytest.raises(ValueError, match="vergeben"):
        auth.register("freightone", PASSWORD)
    assert auth.authenticate("FREIGHTONE", PASSWORD) == user
    for username in ("unknown", "FreightOne"):
        with pytest.raises(ValueError, match="falsch"):
            auth.authenticate(username, "wrong-password")
    token = auth.issue_session(user["id"])
    assert accounts.session_user(token) == user
    with database.connect() as connection:
        digest = connection.execute(
            "SELECT token_hash FROM sessions"
        ).fetchone()
        assert digest[0] != token
    accounts.revoke_session(token)
    assert accounts.session_user(token) is None
    accounts.save_session("expired", user["id"], -10)
    assert accounts.session_user("expired") is None
    accounts.save_session("valid", user["id"], 10)
    with database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM sessions").fetchone()[0]
            == 1
        )
    for _ in range(30):
        assert accounts.allow_attempt("peer")
    assert not accounts.allow_attempt("peer")
    with database.connect() as connection:
        connection.execute("UPDATE auth_attempts SET expires_at = 0")
    assert accounts.allow_attempt("peer")


def test_auth_api_rejects_unsafe_requests_and_sets_private_cookie(auth_api):
    _, client = auth_api
    for path in (
        "dashboard",
        "fleet",
        "contracts",
        "transports",
        "leaderboard",
        "auth/me",
    ):
        assert client.get(f"/api/v1/{path}").status_code == 401

    body = {"username": "Alice", "password": PASSWORD}
    assert client.post("/api/v1/auth/register", json=body).status_code == 403
    client.headers["X-Freight-Request"] = "1"
    response = client.post(
        "/api/v1/auth/register",
        json=body,
        headers={"Origin": "https://evil.test"},
    )
    assert response.status_code == 403
    invalid = client.post(
        "/api/v1/auth/register",
        json={**body, "password": "short"},
    )
    assert invalid.status_code == 422

    response = _register(client, "Alice")
    assert response.status_code == 201
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "password" not in response.text
    assert _register(client, "Alice").status_code == 409
    assert client.get("/api/v1/auth/me").json()["username"] == "Alice"


def test_authenticated_account_exposes_only_valid_initial_resources(auth_api):
    _, client = auth_api
    client.headers["X-Freight-Request"] = "1"
    assert _register(client, "Alice").status_code == 201

    assert client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
    models = client.get("/api/v1/fleet/catalogue").json()["models"]
    assert len(models) == 4
    purchase = client.post(
        "/api/v1/fleet/purchase",
        json={"model_id": "iveco_sway_500", "price_eur": 1},
    )
    assert purchase.status_code == 201
    assert client.get("/api/v1/dashboard").json()["player"]["cash"] == 26000
    invalid = client.post(
        "/api/v1/fleet/purchase",
        json={"model_id": "iveco_sway_500"},
    )
    assert invalid.status_code == 400
    assert client.post("/api/v1/system/reset").status_code == 404
    leaderboard = client.get("/api/v1/leaderboard").json()["players"]
    assert leaderboard[0]["username"] == "Alice"


def test_logout_and_login_rotate_sessions_without_losing_state(auth_api):
    app, client = auth_api
    client.headers["X-Freight-Request"] = "1"
    assert _register(client, "Alice").status_code == 201
    old_token = client.cookies.get(SESSION_COOKIE)
    purchase = client.post(
        "/api/v1/fleet/purchase",
        json={"model_id": "iveco_sway_500", "price_eur": 1},
    )
    assert purchase.status_code == 201

    assert client.post("/api/v1/auth/logout").json() == {"ok": True}
    assert client.get("/api/v1/auth/me").status_code == 401
    assert app.state.auth.accounts.session_user(old_token) is None
    wrong = {"username": "Alice", "password": "wrong-password-42"}
    assert client.post("/api/v1/auth/login", json=wrong).status_code == 401
    body = {"username": "Alice", "password": PASSWORD}
    assert client.post("/api/v1/auth/login", json=body).status_code == 200
    assert client.cookies.get(SESSION_COOKIE) != old_token
    assert client.get("/api/v1/dashboard").json()["player"]["cash"] == 26000
    with patch.object(
        app.state.auth.accounts,
        "allow_attempt",
        return_value=False,
    ):
        assert client.post("/api/v1/auth/login", json=body).status_code == 429


def test_private_game_resources_are_isolated_between_accounts(auth_api):
    app, client = auth_api
    client.headers["X-Freight-Request"] = "1"
    assert _register(client, "Alice").status_code == 201
    purchase = client.post(
        "/api/v1/fleet/purchase",
        json={"model_id": "iveco_sway_500", "price_eur": 1},
    )
    vehicle_id = purchase.json()["id"]
    prepare_client_market(client, app.state.game_runtime)
    alice_contract = client.get(
        "/api/v1/contracts?vehicle_id=truck_01"
    ).json()["contracts"][0]["id"]

    assert _register(client, "Bob").status_code == 201
    assert client.get(f"/api/v1/fleet/{vehicle_id}").status_code == 404
    assert client.get(f"/api/v1/contracts/{alice_contract}").status_code == 404
    assert client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
    prepare_client_market(client, app.state.game_runtime)
    contract = client.get("/api/v1/contracts?vehicle_id=truck_01").json()[
        "contracts"
    ][0]
    trip = client.post(
        f"/api/v1/contracts/{contract['id']}/accept",
        json={"vehicle_id": "truck_01"},
    )
    assert trip.status_code == 200
    trip_id = trip.json()["id"]
    assert client.get(f"/api/v1/transports/{trip_id}").status_code == 200

    body = {"username": "Alice", "password": PASSWORD}
    assert client.post("/api/v1/auth/login", json=body).status_code == 200
    assert client.get(f"/api/v1/transports/{trip_id}").status_code == 404
