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
from app.repositories.game_state import SqliteGameUnitOfWork
from app.services.cost_profiles import VehicleCostResolver
from app.services.dispatch_planning import DispatchPlanningService
from app.services.fleet import FleetService
from app.services.game import GameService


@pytest.fixture
def relational_game(game, tmp_path):
    database = SqliteGameDatabase(tmp_path / "port-state.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES ('owner', 'Owner', 'test-only', 0)"
        )
    service = GameService(
        unit_of_work=SqliteGameUnitOfWork(database, "owner"),
        world=game.world,
        router=game.router,
        dispatch_planning=DispatchPlanningService(
            game.router,
            VehicleCostResolver(game.catalogue),
            game.dispatch_planning.anchors,
            game.world,
        ),
        market=game.market,
        catalogue=game.catalogue,
        market_scope=game.market_scope,
        clock=game.now,
    )
    return service


async def test_relational_game_use_cases_preserve_atomic_settlement(
    relational_game, monkeypatch
):
    game = relational_game
    with pytest.raises(ValueError, match="initialisiert"):
        project_dashboard(game.dashboard())
    fleet = FleetService(game.unit_of_work, game.catalogue, game.world)
    with pytest.raises(ValueError, match="initialisiert"):
        project_vehicle(fleet.purchase("iveco_sway_500"))
    game.ensure_initial_state()
    game.ensure_initial_state()
    purchased = project_vehicle(fleet.purchase("iveco_sway_500"))
    assert len(game.state_repository.list_vehicles()) == 2
    offers = [project_contract(value) for value in game.list_contracts()]
    trip = project_transport(
        await game.dispatch(offers[0]["id"], purchased["id"])
    )
    before = game.state_repository.get_player()
    assert before is not None
    monkeypatch.setattr(game, "now", lambda: trip["arrives_at"])
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
    game = relational_game
    game.ensure_initial_state()
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
    game, monkeypatch
):
    from dataclasses import replace

    from app.domain.contracts import ContractOffer
    from app.domain.game import OwnedVehicle
    from app.domain.results import ContractQuote, GameSnapshot
    from app.domain.transports import RouteSnapshot

    assert isinstance(game.dashboard(), GameSnapshot)
    assert isinstance(game.state(), GameSnapshot)
    offer = game.list_contracts()[0]
    assert isinstance(offer, ContractOffer)
    assert isinstance(game.get_vehicle("truck_01"), OwnedVehicle)
    quote = await game.quote_contract(offer.id, "truck_01")
    assert isinstance(quote, ContractQuote)
    assert isinstance(quote.route, RouteSnapshot)
    player = game.state_repository.get_player()
    original_route = game.router.route

    async def route_while_offer_changes(*coordinates):
        route = await original_route(*coordinates)
        game.state_repository.replace_offers(
            tuple(
                replace(
                    item, rate_eur_per_km_ton=item.rate_eur_per_km_ton + 0.01
                )
                if item.id == offer.id
                else item
                for item in game.state_repository.list_offers()
            )
        )
        return route

    monkeypatch.setattr(game.router, "route", route_while_offer_changes)
    with pytest.raises(ValueError, match="geändert"):
        await game.dispatch(offer.id, "truck_01")
    assert game.state_repository.get_player() == player
    assert game.get_vehicle("truck_01").status == "idle"
    assert game.list_transports() == ()


async def test_quote_routes_missing_snapshot_coordinates_by_facility_uid(
    game,
):
    from dataclasses import replace
    from unittest.mock import patch

    offer = game.state_repository.list_offers()[0]
    game.state_repository.replace_offers(
        (replace(offer, origin=replace(offer.origin, coordinates=None)),)
    )
    with patch.object(
        game.router,
        "route",
        wraps=game.router.route,
    ) as routed:
        quote = await game.quote_contract(offer.id, "truck_01")

    assert quote.contract.origin.coordinates is None
    assert quote.dispatch_route is not None
    assert quote.dispatch_route.pickup.coordinates is None
    assert routed.await_count >= 1
