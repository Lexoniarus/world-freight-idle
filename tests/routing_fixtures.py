"""Explicit ready-route setup for authenticated API integration tests."""

from functools import partial

from fastapi.testclient import TestClient

from app.bootstrap import (
    GameRuntime,
    build_player_service,
    build_preparation_worker,
)
from tests.conftest import FakeRouter, FakeRoutingAnchorResolver


def install_fake_routing(runtime: GameRuntime) -> None:
    """Keep every background and request path away from live providers."""
    runtime.router = FakeRouter()
    runtime.anchors = FakeRoutingAnchorResolver()
    assert runtime.readiness is not None
    runtime.readiness.router = runtime.router
    runtime.readiness.anchors = runtime.anchors


def prepare_client_market(client: TestClient, runtime: GameRuntime) -> None:
    """Prepare one real candidate through readiness on the app event loop."""
    user_id = client.get("/api/v1/auth/me").json()["id"]
    assert client.portal is not None
    client.portal.call(prepare_player_market, runtime, user_id)


async def prepare_player_market(runtime: GameRuntime, user_id: str) -> None:
    """Publish a usable offer through the actual leased stock worker."""
    game = build_player_service(runtime, user_id)
    worker = build_preparation_worker(runtime)
    assert worker.lease is not None
    try:
        for _ in range(4):
            assert await worker.lease.run(partial(worker.process, user_id))
            if game.contract_choices(game.list_contracts()):
                return
        raise AssertionError("Fixture worker did not publish a ready offer.")
    finally:
        await worker.close()
