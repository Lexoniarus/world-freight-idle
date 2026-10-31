"""Explicit ready-route setup for authenticated API integration tests."""

from fastapi.testclient import TestClient

from app.bootstrap import (
    GameRuntime,
    build_player_service,
    build_preparation_worker,
)
from tests.support.routing import FakeRouter, FakeRoutingAnchorResolver


def install_fake_routing(synthetic_runtime: GameRuntime) -> None:
    """Keep every background and request path away from live providers."""
    synthetic_runtime.router = FakeRouter()
    synthetic_runtime.anchors = FakeRoutingAnchorResolver()
    synthetic_runtime.routing_preparation.router = synthetic_runtime.router
    synthetic_runtime.routing_preparation.anchors = synthetic_runtime.anchors


def prepare_client_market(
    client: TestClient, synthetic_runtime: GameRuntime
) -> None:
    """Prepare one real candidate through readiness on the app event loop."""
    user_id = client.get("/api/v1/auth/me").json()["id"]
    assert client.portal is not None
    client.portal.call(prepare_player_market, synthetic_runtime, user_id)


async def prepare_player_market(
    synthetic_runtime: GameRuntime, user_id: str
) -> None:
    """Publish a usable offer through the actual local stock worker."""
    game = build_player_service(synthetic_runtime, user_id)
    worker = build_preparation_worker(synthetic_runtime)
    try:
        for _ in range(4):
            await worker.process(user_id)
            if game.contract_choices(game.list_contracts()):
                return
        raise AssertionError("Fixture worker did not publish a ready offer.")
    finally:
        await worker.close()
