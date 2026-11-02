"""The same use cases operate on relational storage through domain ports."""

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_dashboard,
    project_state,
    project_transport,
    project_vehicle,
)
from app.repositories.game_database import SqliteGameDatabase
from app.services.gameplay.fleet import FleetService
from tests.support.game_clock import set_game_clock
from tests.support.game_service import build_fixture_game
from tests.support.market import seed_test_offers


@pytest.fixture
def relational_game(synthetic_game_context, synthetic_game, tmp_path):
    database = SqliteGameDatabase(tmp_path / "port-state.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES ('owner', 'Owner', 'test-only', 0)"
        )
    return build_fixture_game(
        database,
        "owner",
        synthetic_game_context.world,
        synthetic_game_context.catalogue,
        synthetic_game_context.market_generation,
        synthetic_game.now,
    )


async def test_relational_game_use_cases_preserve_atomic_settlement(
    relational_game, monkeypatch
):
    game = relational_game.service
    with pytest.raises(ValueError, match="initialisiert"):
        project_dashboard(game.dashboard())
    fleet = FleetService(
        game.unit_of_work,
        relational_game.catalogue,
        relational_game.world,
    )
    with pytest.raises(ValueError, match="initialisiert"):
        project_vehicle(fleet.purchase("iveco_sway_500"))
    game.ensure_initial_state()
    game.ensure_initial_state()
    purchased = project_vehicle(fleet.purchase("iveco_sway_500"))
    assert len(game.state_repository.list_vehicles()) == 2
    seed_test_offers(game)
    offers = [project_contract(value) for value in game.list_contracts()]
    trip = project_transport(
        await game.dispatch(offers[0]["id"], purchased["id"])
    )
    before = game.state_repository.get_player()
    assert before is not None
    set_game_clock(game, lambda: trip["arrives_at"])
    assert game.reconcile_arrival()
    assert not game.reconcile_arrival()
    after = game.state_repository.get_player()
    assert after is not None
    assert after.cash == before.cash + trip["payout_eur"]
    assert after.completed == 1
    assert [project_transport(value) for value in game.list_transports()] == []
    saved = game.state_repository.list_transports()
    assert len(saved) == 1 and saved[0].status == "settled"
    project_state(game.reset())
    assert game.state_repository.list_transports() == ()
    assert len([project_vehicle(value) for value in game.list_vehicles()]) == 1


async def test_relational_dispatch_rolls_back_all_mutations(
    relational_game, monkeypatch
):
    game = relational_game.service
    game.ensure_initial_state()
    seed_test_offers(game)
    offer = [project_contract(value) for value in game.list_contracts()][0]
    player = game.state_repository.get_player()
    vehicles = game.state_repository.list_vehicles()

    def fail_write(transport):
        raise RuntimeError("storage failure after debit")

    monkeypatch.setattr(game.state_repository, "save_transport", fail_write)
    with pytest.raises(RuntimeError, match="storage failure"):
        project_transport(await game.dispatch(offer["id"], vehicles[0].id))
    assert game.state_repository.get_player() == player
    assert game.state_repository.list_vehicles() == vehicles
    assert game.state_repository.list_transports() == ()
    assert (
        project_contract(game.get_contract(offer["id"]))["id"] == offer["id"]
    )


async def test_game_workflows_return_typed_values_and_reject_changed_offer(
    synthetic_game, monkeypatch
):
    from dataclasses import replace

    from app.domain.contracts import ContractOffer
    from app.domain.game import OwnedVehicle
    from app.domain.results import ContractQuote, GameSnapshot
    from app.domain.transports import RouteSnapshot

    assert isinstance(synthetic_game.dashboard(), GameSnapshot)
    assert isinstance(synthetic_game.state(), GameSnapshot)
    offer = synthetic_game.list_contracts()[0]
    assert isinstance(offer, ContractOffer)
    assert isinstance(synthetic_game.get_vehicle("truck_01"), OwnedVehicle)
    quote = await synthetic_game.quote_contract(offer.id, "truck_01")
    assert isinstance(quote, ContractQuote)
    assert isinstance(quote.route, RouteSnapshot)
    player = synthetic_game.state_repository.get_player()
    readiness = synthetic_game.player_market.routes.readiness
    original_load = readiness.load
    changed = False

    def load_while_offer_changes(*facilities):
        nonlocal changed
        route = original_load(*facilities)
        if not changed:
            changed = True
            synthetic_game.state_repository.replace_offers(
                tuple(
                    replace(
                        item,
                        rate_eur_per_km_ton=(item.rate_eur_per_km_ton + 0.01),
                    )
                    if item.id == offer.id
                    else item
                    for item in synthetic_game.state_repository.list_offers()
                )
            )

        return route

    monkeypatch.setattr(readiness, "load", load_while_offer_changes)
    with pytest.raises(ValueError, match="geändert"):
        await synthetic_game.dispatch(offer.id, "truck_01")
    assert synthetic_game.state_repository.get_player() == player
    assert synthetic_game.get_vehicle("truck_01").status == "idle"
    assert synthetic_game.list_transports() == ()


async def test_quote_loads_prepared_route_by_facility_identity(
    synthetic_game,
):
    from dataclasses import replace
    from unittest.mock import patch

    offer = synthetic_game.state_repository.list_offers()[0]
    synthetic_game.state_repository.replace_offers(
        (replace(offer, origin=replace(offer.origin, coordinates=None)),)
    )
    readiness = synthetic_game.player_market.routes.readiness
    with patch.object(
        readiness,
        "load",
        wraps=readiness.load,
    ) as loaded:
        quote = await synthetic_game.quote_contract(offer.id, "truck_01")

    assert quote.contract.origin.coordinates is None
    assert quote.dispatch_route is not None
    assert quote.dispatch_route.pickup.coordinates is None
    assert loaded.call_count >= 1
