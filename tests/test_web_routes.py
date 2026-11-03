"""Static product-page routing through the application shell."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)


def test_product_pages_are_distinct_routes(tmp_path: Path):
    create_minimal_static_files(tmp_path)
    application = create_app(build_synthetic_application_settings(tmp_path))
    with TestClient(application) as client:
        client.headers["X-Freight-Request"] = "1"
        expected = {
            "/login": "login.html",
            "/leaderboard": "leaderboard.html",
            "/": "index.html",
            "/contracts": "contracts.html",
            "/contracts/c1": "contract-detail.html",
            "/fleet": "fleet.html",
            "/fleet/truck_01": "fleet-detail.html",
            "/company": "company.html",
            "/transports": "transports.html",
            "/transports/t1": "transport-detail.html",
        }
        for route in expected:
            response = client.get(route)
            assert response.status_code == 200
            assert "world-map-shell" in response.text
