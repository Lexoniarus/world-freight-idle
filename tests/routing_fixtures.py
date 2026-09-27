"""Explicit ready-route setup for authenticated API integration tests."""

from fastapi.testclient import TestClient

from app.bootstrap import GameRuntime, build_player_service
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
    """Publish one delivery from the owned vehicle's actual facility."""
    game = build_player_service(runtime, user_id)
    owned = game.state_repository.list_vehicles()
    fleet = game.market.candidates.resolve_fleet(owned)
    candidates = game.market.candidates.build(
        game.market_scope.resolve(owned), fleet
    )
    candidate = next(
        item
        for item in candidates
        if item.trade.origin.facility_uid == owned[0].facility_uid
    )
    assert runtime.readiness is not None
    relation = await runtime.readiness.prepare(
        candidate.trade.origin.facility_uid,
        candidate.trade.destination.facility_uid,
    )
    assert relation is not None and relation.status == "ready"
    assert game.refresh_market()
