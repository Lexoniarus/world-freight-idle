"""Account isolation, security, persistence and concurrent economy tests."""

import asyncio
import runpy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.game_projection import (
    project_contract,
    project_state,
    project_transport,
    project_vehicle,
)
from app.bootstrap import (
    build_leaderboard_reader,
    build_player_service,
)
from app.domain.contracts import ContractOffer
from app.domain.game import PlayerState
from app.domain.transports import ActiveTransport
from app.main import create_app
from app.repositories.accounts import AccountRepository
from app.repositories.sqlite_store import SqliteStore
from app.services.auth import SESSION_COOKIE, AuthService, PasswordHasher
from app.services.fleet import FleetService
from tests.conftest import BERLIN_UID, FakeRouter
from tests.test_api import make_settings, make_static_files
from tests.test_game import first_berlin_contract
from tests.transport_fixtures import add_transport

PASSWORD = "test-only-password-42"


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


def test_transaction_rolls_back_and_namespaces_isolate(store):
    first = SqliteStore(store.path, "user:first:")
    second = SqliteStore(store.path, "user:second:")
    first.set_json("balance", 50)
    second.set_json("balance", 90)
    with pytest.raises(RuntimeError):
        with first.transaction():
            first.set_json("balance", 1)
            with first.transaction():
                first.set_json("fleet", ["truck"])
            raise RuntimeError("simulated failure")
    assert first.get_json("balance") == 50
    assert first.get_json("fleet") is None
    first.delete_state_keys(("balance",))
    assert first.get_json("balance") is None
    assert second.get_json("balance") == 90


def test_player_service_isolation_and_atomic_purchases(
    runtime, game, catalogue
):
    with runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("alice", "alice", "test-only"),
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("bob", "bob", "test-only"),
        )
    alice = build_player_service(runtime, "alice")
    bob = build_player_service(runtime, "bob")
    assert alice.world is bob.world
    vehicle = project_vehicle(
        FleetService(alice.unit_of_work, catalogue, alice.world).purchase(
            "iveco_sway_500"
        )
    )
    assert alice.get_vehicle(vehicle["id"]).capacity_tons == 24.2
    assert alice.state().player.cash == 26000
    assert bob.state().player.cash == 175000
    assert len(bob.list_vehicles()) == 1
    with pytest.raises(ValueError, match="Nicht genug"):
        project_vehicle(
            FleetService(alice.unit_of_work, catalogue, alice.world).purchase(
                "renault_t_high_520"
            )
        )
    with pytest.raises(ValueError, match="Unbekanntes"):
        project_vehicle(
            FleetService(alice.unit_of_work, catalogue, alice.world).purchase(
                "fake"
            )
        )
    with pytest.raises(KeyError):
        bob.get_vehicle(vehicle["id"])
    restored = build_player_service(runtime, "alice")
    assert project_state(restored.state())["player"]["cash"] == 26000
    assert (
        project_vehicle(restored.get_vehicle(vehicle["id"]))["hub_id"]
        == BERLIN_UID
    )


def test_concurrent_purchases_cannot_overdraw(runtime, game, catalogue):
    with runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("race", "race", "test-only"),
        )
    first = build_player_service(runtime, "race")
    second = build_player_service(runtime, "race")

    def purchase(service):
        try:
            return project_vehicle(
                FleetService(
                    service.unit_of_work, catalogue, service.world
                ).purchase("iveco_sway_500")
            )
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(purchase, [first, second]))
    assert sum(item is not None for item in results) == 1
    assert project_state(first.state())["player"]["cash"] == 26000
    assert (
        len([project_vehicle(value) for value in first.list_vehicles()]) == 2
    )


async def test_parallel_transports_and_offline_settlement(
    game, catalogue, monkeypatch
):
    second_vehicle = project_vehicle(
        FleetService(game.unit_of_work, catalogue, game.world).purchase(
            "iveco_sway_500"
        )
    )
    [project_contract(value) for value in game.refresh_market(force=True)]
    contracts = [
        item
        for item in [
            project_contract(value) for value in game.list_contracts()
        ]
        if item["origin_hub_id"] == BERLIN_UID
    ]
    first = project_transport(
        await game.dispatch(contracts[0]["id"], "truck_01")
    )
    second = project_transport(
        await game.dispatch(contracts[1]["id"], second_vehicle["id"])
    )
    assert (
        len([project_transport(value) for value in game.list_transports()])
        == 2
    )
    before = project_state(game.state())["player"]["cash"]
    monkeypatch.setattr(
        game, "now", lambda: max(first["arrives_at"], second["arrives_at"]) + 1
    )
    assert game.reconcile_arrival()
    assert not game.reconcile_arrival()
    state = project_state(game.state())
    assert state["active_trips"] == []
    assert state["player"]["completed"] == 2
    assert (
        state["player"]["cash"]
        == before + first["payout_eur"] + second["payout_eur"]
    )
    assert all(vehicle["status"] == "idle" for vehicle in state["vehicles"])


async def test_simultaneous_dispatch_revalidates_after_routing(game):
    arrived = asyncio.Event()
    release = asyncio.Event()
    original = game.router.route

    async def slow_route(*args):
        arrived.set()
        await release.wait()
        return await original(*args)

    game.router.route = slow_route
    contract = first_berlin_contract(game)
    task = asyncio.create_task(game.dispatch(contract["id"], "truck_01"))
    await arrived.wait()
    second = asyncio.create_task(game.dispatch(contract["id"], "truck_01"))
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(task, second, return_exceptions=True)
    assert sum(isinstance(result, ActiveTransport) for result in results) == 1
    assert sum(isinstance(result, KeyError) for result in results) == 1
    trip = [project_transport(value) for value in game.list_transports()][0]
    assert (
        project_state(game.state())["player"]["cash"]
        == 175000 - trip["operating_cost_eur"]
    )


async def test_expired_contract_and_failed_routing_do_not_charge(game):
    contract = first_berlin_contract(game)
    game.state_repository.replace_offers(
        tuple(
            ContractOffer.from_dict(item)
            for item in [{**contract, "created_at": 0, "expires_at": 1}]
        )
    )
    with pytest.raises(KeyError):
        project_transport(await game.dispatch(contract["id"], "truck_01"))
    game.state_repository.replace_offers(
        tuple(ContractOffer.from_dict(item) for item in [contract])
    )
    with patch.object(
        game.router, "route", side_effect=RuntimeError("offline")
    ):
        with pytest.raises(RuntimeError):
            project_transport(await game.dispatch(contract["id"], "truck_01"))
    assert project_state(game.state())["player"]["cash"] == 175000
    assert [project_transport(value) for value in game.list_transports()] == []


def test_leaderboard_counts_offline_arrivals_without_double_counting(
    database, runtime, game
):
    accounts = AccountRepository(database)
    alice = accounts.create_user("Alice", "unused")
    accounts.create_user("Bob", "unused")
    service = build_player_service(runtime, alice["id"])
    service.state_repository.save_player(
        PlayerState.from_dict(
            {"cash": 175000, "completed": 2, "reputation": 2}
        )
    )
    add_transport(service, payout=100)
    reader = build_leaderboard_reader(runtime)
    assert list(reader.list_ranking(game.now())) == [
        {"username": "Alice", "completed": 3},
        {"username": "TestOwner", "completed": 0},
        {"username": "Bob", "completed": 0},
    ]
    service.reconcile_arrival()
    assert reader.list_ranking(game.now())[0]["completed"] == 3


def test_auth_api_and_private_game_resources(tmp_path):
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
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
        assert (
            client.post("/api/v1/auth/register", json=body).status_code == 403
        )
        client.headers["X-Freight-Request"] = "1"
        assert (
            client.post(
                "/api/v1/auth/register",
                json=body,
                headers={"Origin": "https://evil.test"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/auth/register", json={**body, "password": "short"}
            ).status_code
            == 422
        )
        response = client.post("/api/v1/auth/register", json=body)
        assert response.status_code == 201
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=strict" in response.headers["set-cookie"].lower()
        assert "password" not in response.text
        old_token = client.cookies.get(SESSION_COOKIE)
        assert (
            client.post("/api/v1/auth/register", json=body).status_code == 409
        )
        assert client.get("/api/v1/auth/me").json()["username"] == "Alice"
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
        )
        models = client.get("/api/v1/fleet/catalogue").json()["models"]
        assert len(models) >= 8
        purchase = client.post(
            "/api/v1/fleet/purchase",
            json={"model_id": "iveco_sway_500", "price_eur": 1},
        )
        assert purchase.status_code == 201
        vehicle_id = purchase.json()["id"]
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 26000
        )
        assert (
            client.post(
                "/api/v1/fleet/purchase", json={"model_id": "iveco_sway_500"}
            ).status_code
            == 400
        )
        assert client.post("/api/v1/system/reset").status_code == 404
        assert (
            client.get("/api/v1/leaderboard").json()["players"][0]["username"]
            == "Alice"
        )
        assert client.post("/api/v1/auth/logout").json() == {"ok": True}
        assert client.get("/api/v1/auth/me").status_code == 401
        assert app.state.auth.accounts.session_user(old_token) is None
        wrong = {**body, "password": "wrong-password-42"}
        assert client.post("/api/v1/auth/login", json=wrong).status_code == 401
        assert client.post("/api/v1/auth/login", json=body).status_code == 200
        assert client.cookies.get(SESSION_COOKIE) != old_token
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 26000
        )
        alice_contract = client.get("/api/v1/contracts").json()["contracts"][
            0
        ]["id"]
        assert (
            client.post(
                "/api/v1/auth/register", json={**body, "username": "Bob"}
            ).status_code
            == 201
        )
        assert client.get(f"/api/v1/fleet/{vehicle_id}").status_code == 404
        assert (
            client.get(f"/api/v1/contracts/{alice_contract}").status_code
            == 404
        )
        assert (
            client.get("/api/v1/dashboard").json()["player"]["cash"] == 175000
        )
        app.state.game.router = FakeRouter()
        contract = client.get("/api/v1/contracts").json()["contracts"][0]
        trip = client.post(
            f"/api/v1/contracts/{contract['id']}/accept",
            json={"vehicle_id": "truck_01"},
        )
        assert trip.status_code == 200
        trip_id = trip.json()["id"]
        assert client.get(f"/api/v1/transports/{trip_id}").status_code == 200
        assert client.post("/api/v1/auth/login", json=body).status_code == 200
        assert client.get(f"/api/v1/transports/{trip_id}").status_code == 404
        with patch.object(
            app.state.auth.accounts, "allow_attempt", return_value=False
        ):
            assert (
                client.post("/api/v1/auth/login", json=body).status_code == 429
            )


def test_launchers_run_main_without_changing_working_directory():
    root = Path(__file__).resolve().parents[1]
    with patch("uvicorn.run") as run:
        runpy.run_path(str(root / "main.py"), run_name="__main__")
        assert run.call_args.args == ("app.main:app",)
        assert run.call_args.kwargs["host"] == "0.0.0.0"


async def test_initialization_does_not_implicitly_import_legacy_trips(
    tmp_path,
):
    import httpx

    from app.bootstrap import build_game_runtime
    from app.domain.errors import UnsupportedGameSchema

    settings = make_settings(tmp_path)
    store = SqliteStore(settings.db_path)
    store.set_json("active_trip", {"id": "old", "arrives_at": 42})
    async with httpx.AsyncClient() as routing_client:
        with pytest.raises(UnsupportedGameSchema):
            build_game_runtime(settings, routing_client)
    assert store.get_json("active_trip") == {"id": "old", "arrives_at": 42}


def test_concurrent_arrivals_pay_once(runtime, game):
    with runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("arrival", "arrival", "test-only"),
        )
    alice = build_player_service(runtime, "arrival")
    other = build_player_service(runtime, "arrival")
    add_transport(alice)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(service.reconcile_arrival)
            for service in (alice, other)
        ]
        assert sorted(future.result() for future in futures) == [False, True]
    assert alice.state().player.cash == 176000
