"""Isolated browser-test server; never used by the production entry point."""

import os
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import Depends

from app.api.v1.dependencies import get_game_service
from app.bootstrap import build_game_runtime
from app.config import Settings
from app.domain.energy import EnergyProfile
from app.main import create_app, lifespan
from app.services.game import GameService
from tests.conftest import (
    FakeRouter,
    FakeRoutingAnchorResolver,
)

temporary = TemporaryDirectory(prefix="world-freight-browser-")
external_database = os.getenv("WFI_BROWSER_DB_PATH")
settings = replace(
    Settings.from_env(),
    db_path=(
        Path(external_database)
        if external_database
        else Path(temporary.name) / "test.db"
    ),
    game_time_scale=900,
)
app = create_app(settings)


@asynccontextmanager
async def browser_lifespan(application):
    def test_runtime(active_settings, client):
        runtime = build_game_runtime(active_settings, client)
        runtime.router = FakeRouter()
        runtime.anchors = FakeRoutingAnchorResolver()
        assert runtime.readiness is not None
        runtime.readiness.router = runtime.router
        runtime.readiness.anchors = runtime.anchors
        return runtime

    with patch("app.main.build_game_runtime", side_effect=test_runtime):
        async with lifespan(application):
            yield
    temporary.cleanup()


app.router.lifespan_context = browser_lifespan


@app.post("/__tests__/preparation-scope")
def pause_previous_test_profiles() -> dict:
    """Keep independent browser cases from accumulating unrelated demand."""
    runtime = app.state.game
    jobs = runtime.preparation_jobs
    assert jobs is not None
    now = runtime.clock()
    with runtime.database.transaction():
        with runtime.database.connect() as connection:
            owners = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT user_id FROM player_states ORDER BY user_id"
                )
            )
        for owner in owners:
            jobs.invalidate(owner, now)
            status = jobs.status(owner)
            assert status is not None
            jobs.finish(owner, status.generation, "ready", now + 86400, now)
    return {"ok": True}


@app.post("/__tests__/energy-fixture")
def prepare_energy_fixture(
    single_stop: bool = False,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Configure short-range test energy solely inside the isolated server."""
    vehicle = game.get_vehicle("truck_01")
    model = next(
        m for m in game.catalogue.list_models() if m.id == vehicle.model_id
    )
    capacity = 1000 if single_stop else 100
    vehicle.apply_model(
        replace(
            model,
            energy=EnergyProfile("electric", "kWh", capacity, 100, 35, 0.1),
        )
    )
    vehicle.refill_energy()
    vehicle.consume_energy(capacity * 0.9)
    offers = game.state_repository.list_offers()
    if offers:
        vehicle.reposition_within_city(offers[0].origin)
    with game.unit_of_work.transaction():
        game.state_repository.save_vehicle(vehicle)
        assert game.market_lifecycle.preparation is not None
        game.market_lifecycle.preparation.request(changed=True)
    return {"vehicle_id": vehicle.id}


@app.post("/__tests__/approach-fixture")
def prepare_approach_fixture(
    game: GameService = Depends(get_game_service),
) -> dict:
    """Place the isolated idle truck away from its saved offer's pickup."""
    vehicle = game.get_vehicle("truck_01")
    offer = game.state_repository.list_offers()[0]
    facility = next(
        item
        for item in game.world.read().facilities
        if item.address.city.city_uid == offer.origin.city.city_uid
        and item.facility_uid != offer.origin.facility_uid
        and item.coordinates is not None
    )
    vehicle.reposition_within_city(facility.location_snapshot())
    with game.unit_of_work.transaction():
        game.state_repository.save_vehicle(vehicle)
        assert game.market_lifecycle.preparation is not None
        game.market_lifecycle.preparation.request(changed=True)
    return {"vehicle_id": vehicle.id, "offer_id": offer.id}
