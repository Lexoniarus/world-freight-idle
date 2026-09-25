"""Isolated browser-test server; never used by the production entry point."""

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import Depends

from app.api.v1.dependencies import get_game_service
from app.config import Settings
from app.domain.energy import EnergyProfile
from app.main import create_app, lifespan
from app.services.game import GameService
from tests.conftest import FakeRouter

temporary = TemporaryDirectory(prefix="world-freight-browser-")
settings = replace(
    Settings.from_env(),
    db_path=Path(temporary.name) / "test.db",
    game_time_scale=900,
)
app = create_app(settings)


@asynccontextmanager
async def browser_lifespan(application):
    async with lifespan(application):
        application.state.game.router = FakeRouter()
        yield
    temporary.cleanup()


app.router.lifespan_context = browser_lifespan


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
    with game.unit_of_work.transaction():
        game.state_repository.save_vehicle(vehicle)
    return {"vehicle_id": vehicle.id}
