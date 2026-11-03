"""Direct-call atomicity and resource cleanup on every lifecycle exit."""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI

from app.domain.errors import CatalogueError
from app.domain.game import PlayerState
from app.main import lifespan


@pytest.mark.parametrize("failure", ["catalogue", "write"])
@pytest.mark.parametrize("existing_player", [False, True])
def test_initialization_direct_failure_is_atomic(
    synthetic_game_context, synthetic_game, failure, existing_player
):
    repository = synthetic_game.state_repository
    repository.reset()
    if existing_player:
        repository.save_player(PlayerState(123, 4, 4))
    before = repository.get_player()
    failures = {
        "catalogue": patch.object(
            synthetic_game_context.catalogue,
            "list_models",
            side_effect=CatalogueError("unavailable"),
        ),
        "write": patch.object(
            repository,
            "save_vehicle",
            side_effect=RuntimeError("write failed"),
        ),
    }
    with failures[failure], pytest.raises((CatalogueError, RuntimeError)):
        synthetic_game.ensure_initial_state()
    assert repository.get_player() == before
    assert repository.list_vehicles() == ()
    synthetic_game.ensure_initial_state()
    player = repository.get_player()
    vehicles = repository.list_vehicles()
    synthetic_game.ensure_initial_state()
    assert repository.get_player() == player
    assert repository.list_vehicles() == vehicles
    assert player.cash == (123 if existing_player else 175000)


def test_initialization_creates_no_market_stock(synthetic_game):
    synthetic_game.state_repository.reset()
    assert not hasattr(synthetic_game.market_lifecycle.generation, "generate")
    synthetic_game.ensure_initial_state()
    assert synthetic_game.state_repository.list_offers() == ()


def test_reset_failure_restores_deleted_state(
    synthetic_game_context, synthetic_game
):
    repository = synthetic_game.state_repository
    player = repository.get_player()
    vehicles = repository.list_vehicles()
    offers = repository.list_offers()
    with patch.object(
        synthetic_game_context.catalogue,
        "list_models",
        side_effect=CatalogueError("catalogue failed"),
    ):
        with pytest.raises(CatalogueError):
            synthetic_game.reset()
    assert repository.get_player() == player
    assert repository.list_vehicles() == vehicles
    assert repository.list_offers() == offers


@pytest.mark.parametrize(
    "failure",
    [
        "none",
        "first-client",
        "game",
        "accounts",
        "auth",
        "preferences",
        "world",
        "catalogue",
        "body",
        "close-first",
    ],
)
async def test_lifespan_cleans_up_partial_start_and_shutdown(failure):
    clients = [
        SimpleNamespace(aclose=AsyncMock()),
    ]
    worker = SimpleNamespace(start=AsyncMock(), close=AsyncMock())
    app = FastAPI()
    app.state.settings = SimpleNamespace(request_timeout_seconds=1)
    error = RuntimeError("injected failure")
    creation: list[SimpleNamespace | RuntimeError] = list(clients)
    if failure == "first-client":
        creation[0] = error
    if failure == "close-first":
        clients[0].aclose.side_effect = error
    with ExitStack() as patches:
        patches.enter_context(
            patch("app.main.httpx.AsyncClient", side_effect=creation)
        )
        runtime_factory = patches.enter_context(
            patch(
                "app.main.build_game_runtime",
                side_effect=error if failure == "game" else None,
                return_value=SimpleNamespace(
                    database=Mock(), world=Mock(), catalogue=Mock()
                ),
            )
        )
        patches.enter_context(
            patch(
                "app.main.AccountRepository",
                side_effect=error if failure == "accounts" else None,
            )
        )
        patches.enter_context(
            patch(
                "app.main.AuthService",
                side_effect=error if failure == "auth" else None,
            )
        )
        patches.enter_context(
            patch(
                "app.main.build_preferences",
                side_effect=error if failure == "preferences" else None,
            )
        )
        patches.enter_context(
            patch("app.main.build_preparation_worker", return_value=worker)
        )
        if failure == "world":
            runtime_factory.return_value.world.read.side_effect = error
        if failure == "catalogue":
            runtime_factory.return_value.catalogue.list_models.side_effect = (
                error
            )
        if failure == "none":
            async with lifespan(app):
                assert all(
                    client.aclose.await_count == 0 for client in clients
                )
        else:
            with pytest.raises(RuntimeError, match="injected failure"):
                async with lifespan(app):
                    if failure == "body":
                        raise error
    expected = [0] if failure == "first-client" else [1]
    assert [client.aclose.await_count for client in clients] == expected
    reached_worker = failure in {"none", "body", "close-first"}
    assert worker.start.await_count == int(reached_worker)
    assert worker.close.await_count == int(reached_worker)
