"""The same use cases operate on relational storage through domain ports."""

import pytest

from app.bootstrap import game_store
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.services.fleet import FleetService
from app.services.game import GameService
from tests.transport_fixtures import add_transport


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
        market=game.market,
        pricing=game.pricing,
        catalogue=game.catalogue,
        market_scope=game.market_scope,
    )
    return service


async def test_relational_game_use_cases_preserve_atomic_settlement(
    relational_game, monkeypatch
):
    game = relational_game
    with pytest.raises(ValueError, match="initialisiert"):
        game.dashboard()
    fleet = FleetService(game.unit_of_work, game.catalogue, game.world)
    with pytest.raises(ValueError, match="initialisiert"):
        fleet.purchase("iveco_sway_500")
    with pytest.raises(TypeError, match="KV"):
        game_store(game)
    game.ensure_initial_state()
    game.ensure_initial_state()
    purchased = fleet.purchase("iveco_sway_500")
    assert len(game.state_repository.list_vehicles()) == 2
    offers = game.list_contracts()
    trip = await game.dispatch(offers[0]["id"], purchased["id"])
    before = game.state_repository.get_player()
    assert before is not None
    monkeypatch.setattr(game, "now", lambda: trip["arrives_at"])
    assert game.reconcile_arrival()
    assert not game.reconcile_arrival()
    after = game.state_repository.get_player()
    assert after is not None
    assert after.cash == before.cash + trip["payout_eur"]
    assert after.completed == 1
    assert game.list_transports() == []
    saved = game.state_repository.list_transports()
    assert len(saved) == 1 and saved[0].status == "settled"
    game.reset()
    assert game.state_repository.list_transports() == ()
    assert len(game.list_vehicles()) == 1


async def test_relational_dispatch_rolls_back_all_mutations(
    relational_game, monkeypatch
):
    game = relational_game
    game.ensure_initial_state()
    offer = game.list_contracts()[0]
    player = game.state_repository.get_player()
    vehicles = game.state_repository.list_vehicles()

    def fail_write(transport):
        raise RuntimeError("storage failure after debit")

    monkeypatch.setattr(game.state_repository, "save_transport", fail_write)
    with pytest.raises(RuntimeError, match="storage failure"):
        await game.dispatch(offer["id"], vehicles[0].id)
    assert game.state_repository.get_player() == player
    assert game.state_repository.list_vehicles() == vehicles
    assert game.state_repository.list_transports() == ()
    assert game.get_contract(offer["id"])["id"] == offer["id"]


def test_transition_adapter_roundtrips_without_implicit_migration(game):
    repository = game.state_repository
    player = repository.get_player()
    vehicles = repository.list_vehicles()
    offers = repository.list_offers()
    assert player is not None and vehicles and offers
    with pytest.raises(RuntimeError):
        with game.unit_of_work.transaction():
            repository.reset()
            assert repository.get_player() is None
            raise RuntimeError("rollback")
    assert repository.get_player() == player
    repository.save_player(player)
    repository.save_vehicle(vehicles[0])
    repository.replace_offers(offers)
    repository.remove_offer("absent")
    assert repository.list_offers() == offers
    trip = add_transport(game)
    repository.save_transport(trip.settle(3))
    assert repository.list_transports()[0].status == "settled"
    game_store(game).set_json("contracts", [{"id": "incomplete"}])
    with pytest.raises(KeyError):
        repository.list_offers()
    game_store(game).set_json("active_trips", [{"id": "incomplete"}])
    with pytest.raises(KeyError):
        repository.list_transports()
