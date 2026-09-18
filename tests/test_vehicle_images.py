"""Photo provenance and narrowly scoped profile maintenance."""

import sqlite3

import pytest

from app.services.vehicle_presentation import present_vehicles


def test_images_preserve_provenance_and_never_change_gameplay(catalogue):
    models = catalogue.list_models()
    assert all(model.image for model in models)
    model = models[0]
    vehicle = {
        "id": "owned",
        "model_id": model.id,
        "capacity_tons": 99,
        "name": "Custom",
    }
    result = present_vehicles([vehicle], catalogue)[0]
    assert result["image"]["url"].startswith("https://upload.wikimedia.org/")
    assert result["image"]["author"]
    assert result["image"]["license_name"] == "CC0 1.0"
    assert result["image"]["scope"] == "model_family"
    assert result["capacity_tons"] == 99 and result["name"] == "Custom"
    assert "image" not in vehicle
    catalogue.path.rename(catalogue.path.with_suffix(".unavailable"))
    assert present_vehicles([vehicle], catalogue)[0]["image"] is None


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "https://[broken", "https://elsewhere.test/a.jpg"],
)
def test_invalid_image_links_do_not_break_catalogue(catalogue, url):
    with sqlite3.connect(catalogue.path) as db:
        db.execute("UPDATE vehicle_images SET direct_image_url=?", (url,))
    assert all(model.image is None for model in catalogue.list_models())


def test_unverified_images_are_not_presented(catalogue):
    with sqlite3.connect(catalogue.path) as db:
        db.execute("UPDATE vehicle_images SET verification_status='pending'")
    assert all(model.image is None for model in catalogue.list_models())


def test_image_selection_prefers_verified_primary(catalogue):
    with sqlite3.connect(catalogue.path) as db:
        db.execute(
            "UPDATE vehicle_images SET is_primary=0 WHERE vehicle_id='iveco_sway_500'"
        )
        db.execute("""INSERT INTO vehicle_images(vehicle_id,source_id,license_id,direct_image_url,
            author,attribution_text,image_scope,verification_status,is_primary)
            SELECT vehicle_id,source_id,license_id,direct_image_url,'Selected photographer',
                attribution_text,image_scope,verification_status,1 FROM vehicle_images
            WHERE vehicle_id='iveco_sway_500'""")
    assert catalogue.list_models()[0].image.author == "Selected photographer"
