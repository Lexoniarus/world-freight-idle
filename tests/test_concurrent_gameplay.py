"""Account isolation, security, persistence and concurrent economy tests."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_state,
    project_transport,
    project_vehicle,
)
from app.bootstrap import build_player_context
from app.domain.transports import ActiveTransport
from app.services.gameplay.fleet import FleetService
from tests.support.catalogues import BERLIN_UID
from tests.support.game import first_berlin_contract
from tests.support.game_clock import set_game_clock
from tests.transport_fixtures import add_transport

PASSWORD = "test-only-password-42"


def test_concurrent_purchases_cannot_overdraw(
    synthetic_runtime, synthetic_game, synthetic_vehicle_catalogue
):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("race", "race", "test-only"),
        )
    first = build_player_context(synthetic_runtime, "race")
    second = build_player_context(synthetic_runtime, "race")

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
    assert project_state(first.game.state())["player"]["cash"] == 26000
    assert (
        len([project_vehicle(value) for value in first.game.list_vehicles()])
        == 2
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
    readiness = synthetic_game.player_market.routes.readiness
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


def test_concurrent_arrivals_pay_once(synthetic_runtime, synthetic_game):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("arrival", "arrival", "test-only"),
        )
    alice_context = build_player_context(synthetic_runtime, "arrival")
    other_context = build_player_context(synthetic_runtime, "arrival")
    alice = alice_context.game
    other = other_context.game
    add_transport(alice, context=alice_context)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(service.reconcile_arrival)
            for service in (alice, other)
        ]
        assert sorted(future.result() for future in futures) == [False, True]
    assert alice.state().player.cash == 176000
