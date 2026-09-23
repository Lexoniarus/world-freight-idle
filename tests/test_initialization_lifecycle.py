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
    game, failure, existing_player
):
    repository = game.state_repository
    repository.reset()
    if existing_player:
        repository.save_player(PlayerState(123, 4, 4))
    before = repository.get_player()
    failures = {
        "catalogue": patch.object(
            game.catalogue,
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
        game.ensure_initial_state()
    assert repository.get_player() == before
    assert repository.list_vehicles() == ()
    game.ensure_initial_state()
    player = repository.get_player()
    vehicles = repository.list_vehicles()
    game.ensure_initial_state()
    assert repository.get_player() == player
    assert repository.list_vehicles() == vehicles
    assert player.cash == (123 if existing_player else 175000)


def test_initialization_defers_market_generation(game):
    game.state_repository.reset()
    with patch.object(type(game.market), "generate") as generate:
        game.ensure_initial_state()
    generate.assert_not_called()
    assert game.state_repository.list_offers() == ()


def test_reset_failure_restores_deleted_state(game):
    repository = game.state_repository
    player = repository.get_player()
    vehicles = repository.list_vehicles()
    offers = repository.list_offers()
    with patch.object(
        type(game.market),
        "generate",
        side_effect=RuntimeError("market failed"),
    ):
        with pytest.raises(RuntimeError):
            game.reset()
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
        "body",
        "close-first",
    ],
)
async def test_lifespan_cleans_up_partial_start_and_shutdown(failure):
    clients = [
        SimpleNamespace(aclose=AsyncMock()),
    ]
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
        patches.enter_context(
            patch(
                "app.main.build_game_runtime",
                side_effect=error if failure == "game" else None,
                return_value=SimpleNamespace(database=Mock()),
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
