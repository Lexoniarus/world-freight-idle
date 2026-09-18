"""Isolated browser-test server; never used by the production entry point."""

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.main import create_app, lifespan
from tests.conftest import FakeGeocoder, FakeRouter

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
        application.state.game.geocoder = FakeGeocoder()
        application.state.game.router = FakeRouter()
        yield
    temporary.cleanup()


app.router.lifespan_context = browser_lifespan
