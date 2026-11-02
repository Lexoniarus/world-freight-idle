"""Production-shaped composition for routing integration scenarios."""

from pathlib import Path
from types import SimpleNamespace

from app.domain.ports import WorldCatalogue
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import SqliteRoutingReadinessStore
from app.services.routing.evidence import RoutingEvidenceReader
from app.services.routing.preparation import RoutingPreparationService
from tests.support.routing import (
    FakeRouter,
    FakeRoutingAnchorResolver,
    RoutingTestHarness,
)


def build_routing_test_case(
    directory: Path,
    world: WorldCatalogue,
) -> SimpleNamespace:
    """Compose one isolated routing read/preparation integration boundary."""
    database = SqliteGameDatabase(directory / "game.db")
    database.initialize()
    cache = SqliteProviderCache(database)
    store = SqliteRoutingReadinessStore(database)
    anchors = SqliteRoutingAnchorRepository(database)
    clock = [100.0]
    anchor_resolver = FakeRoutingAnchorResolver()
    router = FakeRouter()
    evidence = RoutingEvidenceReader(
        store,
        anchors,
        world,
        "fake",
        lambda: clock[0],
        anchor_resolver.max_snap_distance_m,
    )
    preparation = RoutingPreparationService(
        evidence,
        store,
        anchor_resolver,
        router,
        world,
        lambda: clock[0],
    )
    return SimpleNamespace(
        db=database,
        cache=cache,
        store=store,
        anchors=anchors,
        clock=clock,
        service=RoutingTestHarness(evidence, preparation),
    )
