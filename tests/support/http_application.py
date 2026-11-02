"""Small HTTP application harnesses for owner-focused API tests."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.main import create_app
from tests.support.api import FakeGame, create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)


@contextmanager
def fake_game_api_client(
    tmp_path: Path,
    synthetic_game,
) -> Iterator[TestClient]:
    """Expose one deterministic game facade through the real HTTP router."""
    create_minimal_static_files(tmp_path)
    application = create_app(build_synthetic_application_settings(tmp_path))
    with TestClient(application) as client:
        application.dependency_overrides[get_game_service] = lambda: FakeGame(
            synthetic_game
        )
        client.headers["X-Freight-Request"] = "1"
        yield client
