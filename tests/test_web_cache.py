"""Browser shell cache policy regression tests."""

from fastapi.testclient import TestClient

from app.main import create_app
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)


def test_application_shell_disables_browser_cache(tmp_path):
    create_minimal_static_files(tmp_path)
    app = create_app(build_synthetic_application_settings(tmp_path))
    with TestClient(app) as client:
        for route in (
            "/login",
            "/leaderboard",
            "/",
            "/contracts",
            "/contracts/c1",
            "/fleet",
            "/transports",
            "/transports/t1",
        ):
            response = client.get(route)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
