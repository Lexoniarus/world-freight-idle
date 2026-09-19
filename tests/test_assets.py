"""Static game-asset delivery."""

from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_api import make_settings, make_static_files


def test_vehicle_asset_directory_is_served(tmp_path):
    """Serve repository vehicle sprites outside the Vite build output."""
    make_static_files(tmp_path)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "probe.svg").write_text("<svg></svg>", encoding="utf-8")
    with TestClient(create_app(make_settings(tmp_path))) as client:
        response = client.get("/assets/probe.svg")
        assert response.status_code == 200
        assert response.text == "<svg></svg>"
