"""Account isolation, security, persistence and concurrent economy tests."""

import asyncio
import runpy
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
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
from app.domain.game import PlayerState
from app.domain.transports import ActiveTransport
from app.main import create_app
from app.repositories.accounts import AccountRepository
from app.services.auth import SESSION_COOKIE, AuthService, PasswordHasher
from app.services.gameplay.fleet import FleetService
from tests.routing_fixtures import (
    install_fake_routing,
    prepare_client_market,
)
from tests.support.api import make_settings, make_static_files
from tests.support.catalogues import BERLIN_UID
from tests.support.game import first_berlin_contract
from tests.support.game_clock import set_game_clock
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


def test_player_service_isolation_and_atomic_purchases(
    synthetic_runtime, synthetic_game, synthetic_vehicle_catalogue
):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("alice", "alice", "test-only"),
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("bob", "bob", "test-only"),
        )
    alice = build_player_service(synthetic_runtime, "alice")
    bob = build_player_service(synthetic_runtime, "bob")
    assert alice.market_lifecycle.scope.world is synthetic_runtime.world
    assert bob.market_lifecycle.scope.world is synthetic_runtime.world
    vehicle = project_vehicle(
        FleetService(
            alice.unit_of_work,
            synthetic_vehicle_catalogue,
            synthetic_runtime.world,
        ).purchase("iveco_sway_500")
    )
    assert alice.get_vehicle(vehicle["id"]).capacity_tons == 24.2
    assert alice.state().player.cash == 26000
    assert bob.state().player.cash == 175000
    assert len(bob.list_vehicles()) == 1
    with pytest.raises(ValueError, match="Nicht genug"):
        project_vehicle(
            FleetService(
                alice.unit_of_work,
                synthetic_vehicle_catalogue,
                synthetic_runtime.world,
            ).purchase("renault_t_high_520")
        )
    with pytest.raises(ValueError, match="Unbekanntes"):
        project_vehicle(
            FleetService(
                alice.unit_of_work,
                synthetic_vehicle_catalogue,
                synthetic_runtime.world,
            ).purchase("fake")
        )
    with pytest.raises(KeyError):
        bob.get_vehicle(vehicle["id"])
    restored = build_player_service(synthetic_runtime, "alice")
    assert project_state(restored.state())["player"]["cash"] == 26000
    assert (
        project_vehicle(restored.get_vehicle(vehicle["id"]))["hub_id"]
        == BERLIN_UID
    )


def test_concurrent_purchases_cannot_overdraw(
    synthetic_runtime, synthetic_game, synthetic_vehicle_catalogue
):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("race", "race", "test-only"),
        )
    first = build_player_service(synthetic_runtime, "race")
    second = build_player_service(synthetic_runtime, "race")

    def purchase(service):
        try:
            return project_vehicle(
                FleetService(
                    service.unit_of_work,
                    synthetic_vehicle_catalogue,
                    synthetic_runtime.world,
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
    synthetic_game_context, synthetic_game, synthetic_vehicle_catalogue
):
    second_vehicle = project_vehicle(
        FleetService(
            synthetic_game.unit_of_work,
            synthetic_vehicle_catalogue,
            synthetic_game_context.world,
        ).purchase("iveco_sway_500")
    )
    [project_contract(value) for value in synthetic_game.refresh_contracts()]
    contracts = [
        item
        for item in [
            project_contract(value)
            for value in synthetic_game.list_contracts()
        ]
        if item["origin_hub_id"] == BERLIN_UID
    ]
    first = project_transport(
        await synthetic_game.dispatch(contracts[0]["id"], "truck_01")
    )
    second = project_transport(
        await synthetic_game.dispatch(contracts[1]["id"], second_vehicle["id"])
    )
    assert (
        len(
            [
                project_transport(value)
                for value in synthetic_game.list_transports()
            ]
        )
        == 2
    )
    before = project_state(synthetic_game.state())["player"]["cash"]
    set_game_clock(
        synthetic_game,
        lambda: max(first["arrives_at"], second["arrives_at"]) + 1,
    )
    assert synthetic_game.reconcile_arrival()
    assert not synthetic_game.reconcile_arrival()
    state = project_state(synthetic_game.state())
    assert state["active_trips"] == []
    assert state["player"]["completed"] == 2
    assert (
        state["player"]["cash"]
        == before + first["payout_eur"] + second["payout_eur"]
    )
    assert all(vehicle["status"] == "idle" for vehicle in state["vehicles"])


async def test_simultaneous_dispatch_revalidates_after_routing(synthetic_game):
    arrived = asyncio.Event()
    release = asyncio.Event()
    original = type(synthetic_game.transport_dispatch).quote_contract

    async def slow_quote(service, *args):
        quote = await original(service, *args)
        arrived.set()
        await release.wait()
        return quote

    contract = first_berlin_contract(synthetic_game)
    with patch.object(
        type(synthetic_game.transport_dispatch),
        "quote_contract",
        slow_quote,
    ):
        task = asyncio.create_task(
            synthetic_game.dispatch(contract["id"], "truck_01")
        )
        await arrived.wait()
        second = asyncio.create_task(
            synthetic_game.dispatch(contract["id"], "truck_01")
        )
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(task, second, return_exceptions=True)
    assert sum(isinstance(result, ActiveTransport) for result in results) == 1
    assert sum(isinstance(result, KeyError) for result in results) == 1
    trip = [
        project_transport(value) for value in synthetic_game.list_transports()
    ][0]
    assert (
        project_state(synthetic_game.state())["player"]["cash"]
        == 175000 - trip["operating_cost_eur"]
    )


async def test_expired_contract_and_failed_routing_do_not_charge(
    synthetic_game,
):
    contract = synthetic_game.transport_dispatch.find_contract(
        first_berlin_contract(synthetic_game)["id"]
    )
    synthetic_game.state_repository.replace_offers(
        (replace(contract, created_at=0, expires_at=1),)
    )
    with pytest.raises(KeyError):
        project_transport(
            await synthetic_game.dispatch(contract.id, "truck_01")
        )
    synthetic_game.state_repository.replace_offers((contract,))
    readiness = synthetic_game.market_services.routes.readiness
    with patch.object(
        readiness,
        "load",
        side_effect=RuntimeError("offline"),
    ):
        with pytest.raises(RuntimeError):
            project_transport(
                await synthetic_game.dispatch(contract.id, "truck_01")
            )
    assert project_state(synthetic_game.state())["player"]["cash"] == 175000
    assert [
        project_transport(value) for value in synthetic_game.list_transports()
    ] == []


def test_leaderboard_counts_offline_arrivals_without_double_counting(
    database, synthetic_runtime, synthetic_game
):
    accounts = AccountRepository(database)
    alice = accounts.create_user("Alice", "unused")
    accounts.create_user("Bob", "unused")
    service = build_player_service(synthetic_runtime, alice["id"])
    service.state_repository.save_player(
        PlayerState(cash=175000, completed=2, reputation=2)
    )
    add_transport(service, payout=100)
    reader = build_leaderboard_reader(synthetic_runtime)
    assert list(reader.list_ranking(synthetic_game.now())) == [
        {"username": "Alice", "completed": 3},
        {"username": "TestOwner", "completed": 0},
        {"username": "Bob", "completed": 0},
    ]
    service.reconcile_arrival()
    assert reader.list_ranking(synthetic_game.now())[0]["completed"] == 3


def test_auth_api_and_private_game_resources(tmp_path):
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        install_fake_routing(app.state.game_runtime)
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
        prepare_client_market(client, app.state.game_runtime)
        alice_contract = client.get(
            "/api/v1/contracts?vehicle_id=truck_01"
        ).json()["contracts"][0]["id"]
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
    with (
        patch("app.launcher.run", return_value=0) as run,
        patch("sys.argv", ["main.py"]),
        pytest.raises(SystemExit) as exited,
    ):
        runpy.run_path(str(root / "main.py"), run_name="__main__")
    assert exited.value.code == 0
    run.assert_called_once_with()


async def test_initialization_does_not_implicitly_import_legacy_trips(
    tmp_path,
):
    import httpx

    from app.bootstrap import build_game_runtime
    from app.domain.errors import UnsupportedGameSchema

    settings = make_settings(tmp_path)
    import sqlite3

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(settings.db_path)) as connection, connection:
        connection.execute(
            "CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.execute(
            "INSERT INTO kv VALUES (?, ?)",
            ("active_trip", '{"id":"old","arrives_at":42}'),
        )
    original = settings.db_path.read_bytes()
    async with httpx.AsyncClient() as routing_client:
        with pytest.raises(UnsupportedGameSchema):
            build_game_runtime(settings, routing_client)
    assert settings.db_path.read_bytes() == original


def test_concurrent_arrivals_pay_once(synthetic_runtime, synthetic_game):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("arrival", "arrival", "test-only"),
        )
    alice = build_player_service(synthetic_runtime, "arrival")
    other = build_player_service(synthetic_runtime, "arrival")
    add_transport(alice)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(service.reconcile_arrival)
            for service in (alice, other)
        ]
        assert sorted(future.result() for future in futures) == [False, True]
    assert alice.state().player.cash == 176000
