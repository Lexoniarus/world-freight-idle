"""Static game-asset delivery."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)


def test_vehicle_asset_directory_is_served(tmp_path):
    """Serve repository vehicle sprites outside the Vite build output."""
    create_minimal_static_files(tmp_path)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "probe.svg").write_text("<svg></svg>", encoding="utf-8")
    settings = build_synthetic_application_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/assets/probe.svg")
        assert response.status_code == 200
        assert response.text == "<svg></svg>"


def test_all_selected_vehicle_assets_are_served_unchanged(tmp_path):
    """Serve each captured view recursively; reject missing and old paths."""
    root = Path(__file__).resolve().parents[1]
    inventory = json.loads(
        (root / "assets/inventory.json").read_text(encoding="utf-8")
    )["files"]
    settings = replace(
        build_synthetic_application_settings(tmp_path),
        base_dir=root,
    )
    with TestClient(create_app(settings)) as client:
        for entry in inventory:
            if entry["usage"] == "reference":
                continue
            response = client.get("/" + entry["target_path"])
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("image/svg+xml")
            assert (
                hashlib.sha256(response.content).hexdigest()
                == (entry["sha256"])
            )
            assert client.get("/" + entry["original_path"]).status_code == 404
        assert (
            client.get("/assets/vehicles/missing/map.svg").status_code == 404
        )
