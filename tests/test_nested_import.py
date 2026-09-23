"""Nested legacy fields are either retained or rejected before writing."""

import copy
import json
import logging
import re
from dataclasses import asdict

import pytest

from app.domain.errors import PersistenceError
from app.repositories.legacy_import_mapping import (
    LegacyFieldError,
    read_documented_cargo,
    read_legacy_good,
    read_legacy_profile,
    read_legacy_route,
    read_legacy_source,
    read_legacy_sources,
    require_legacy_array,
)
from tests.test_game_import import legacy_source as legacy_source
from tests.test_game_import import update_legacy

SOURCE = {
    "url": "https://example.test/evidence",
    "role": "official",
    "verified_at": None,
    "precision": "site",
    "provider": "fixture",
}
GOOD = {"description": "Steel", "cargo_code": "10", "source": SOURCE}
CARGO = {
    "code": "10",
    "name": "Steel",
    "role": "output",
    "standard": True,
    "evidence_type": "official",
    "source": SOURCE,
}


def test_nested_import_values_preserve_optional_metadata(legacy_source):
    _, importer, state, _, _ = legacy_source
    original = copy.deepcopy(state["contracts"][0]["origin"])
    original["company"].update(
        website="https://example.test", sources=[SOURCE]
    )
    original.update(sources=[SOURCE], handled_goods=[GOOD], cargo=[CARGO])
    loaded = importer.reader.location(original)
    assert loaded.company.website == original["company"]["website"]
    assert asdict(loaded.company.sources[0]) == SOURCE
    assert asdict(loaded.sources[0]) == SOURCE
    assert asdict(loaded.handled_goods[0]) == GOOD
    assert asdict(loaded.handling_evidence[0]) == CARGO
    assert loaded.coordinates.latitude == original["lat"]
    assert loaded.catalogue_version == original["catalogue_version"]
    assert read_legacy_sources([], "sources") == ()
    assert require_legacy_array([], "array") == []
    minimal = {"url": SOURCE["url"], "role": "official", "verified_at": None}
    assert read_legacy_source(minimal, "source").precision is None
    assert read_documented_cargo({**CARGO, "source": None}).source is None


def test_nested_location_objects_reject_unknown_fields_and_shapes(
    legacy_source,
):
    _, importer, state, _, _ = legacy_source
    original = copy.deepcopy(state["contracts"][0]["origin"])
    profile = state["contracts"][0]["origin_cargo_evidence"]
    original["company"]["sources"] = [SOURCE]
    original.update(
        sources=[SOURCE],
        coordinate_evidence=[SOURCE],
        handled_goods=[GOOD],
        cargo=[profile, CARGO],
    )
    paths = [
        ("company",),
        ("company", "sources", 0),
        ("sources", 0),
        ("coordinate_evidence", 0),
        ("handled_goods", 0),
        ("handled_goods", 0, "source"),
        ("cargo", 0),
        ("cargo", 1),
        ("cargo", 1, "source"),
    ]
    for path in paths:
        for replacement in ("not-an-object", {"unexpected": "SECRET-VALUE"}):
            value = copy.deepcopy(original)
            parent = value
            diagnostic = "location"
            for key in path[:-1]:
                parent = parent[key]
            for key in path:
                diagnostic += f"[{key}]" if isinstance(key, int) else "." + key
            if isinstance(replacement, dict):
                parent[path[-1]] = {**parent[path[-1]], **replacement}
            else:
                parent[path[-1]] = replacement
            with pytest.raises(
                LegacyFieldError, match=re.escape(diagnostic)
            ) as failure:
                importer.reader.location(value)
            assert "SECRET-VALUE" not in str(failure.value)
    for field in (
        "sources",
        "coordinate_evidence",
        "handled_goods",
        "cargo",
        "aliases",
    ):
        with pytest.raises(LegacyFieldError, match="location." + field):
            importer.reader.location({**original, field: {}})
    with pytest.raises(LegacyFieldError, match="company.sources"):
        importer.reader.location(
            {**original, "company": {**original["company"], "sources": None}}
        )
    with pytest.raises(ValueError, match="city_uid"):
        importer.reader.location({**original, "city_uid": "conflicting"})
    vehicle = copy.deepcopy(state["vehicles"][0])
    vehicle["hub"]["label"] = "conflicting"
    with pytest.raises(ValueError, match="hub"):
        importer.reader.vehicle(vehicle)


def test_nested_cargo_sources_and_arrays_reject_unknown_values(legacy_source):
    _, _, state, _, _ = legacy_source
    profile = copy.deepcopy(state["contracts"][0]["origin_cargo_evidence"])
    profile["source"] = SOURCE
    source = read_legacy_profile(profile).source
    assert source is not None
    assert asdict(source) == SOURCE
    for reader, value, path in (
        (read_legacy_source, SOURCE, "source"),
        (read_legacy_good, GOOD, "good"),
        (read_documented_cargo, CARGO, "cargo"),
        (read_legacy_profile, profile, "profile"),
    ):
        for invalid in (None, [], {**value, "unknown": "SECRET"}):
            with pytest.raises(LegacyFieldError, match=path):
                reader(json.loads(json.dumps(invalid)), path)
    with pytest.raises(LegacyFieldError, match="ancestor_row_ids"):
        read_legacy_profile({**profile, "ancestor_row_ids": {}})
    with pytest.raises(LegacyFieldError, match="cargo.source"):
        read_documented_cargo({**CARGO, "source": []})
    with pytest.raises(LegacyFieldError, match="cargo.source"):
        read_legacy_profile({**profile, "source": {**SOURCE, "unknown": 1}})
    with pytest.raises(LegacyFieldError, match="sources"):
        read_legacy_sources({}, "sources")


def test_legacy_route_rejects_unretained_feature_metadata():
    line = {"type": "LineString", "coordinates": [[13, 52], [9, 53]]}
    assert read_legacy_route(line, "route") == ((13, 52), (9, 53))
    for properties in ({}, None):
        assert read_legacy_route(
            {"type": "Feature", "geometry": line, "properties": properties},
            "route",
        ) == ((13, 52), (9, 53))
    for invalid, path in (
        ([], "route"),
        ({**line, "unknown": 1}, "route"),
        (
            {"type": "Feature", "geometry": {**line, "unknown": 1}},
            "route.geometry",
        ),
        (
            {"type": "Feature", "geometry": line, "properties": {"secret": 1}},
            "route.properties",
        ),
        (
            {"type": "Feature", "geometry": line, "properties": []},
            "route.properties",
        ),
        ({**line, "coordinates": {}}, "route.coordinates"),
        ({**line, "coordinates": [None]}, "route.coordinates[0]"),
        ({**line, "coordinates": [[1, 2, 3]]}, "route.coordinates[0]"),
    ):
        with pytest.raises(LegacyFieldError, match=re.escape(path)):
            read_legacy_route(json.loads(json.dumps(invalid)), "route")


def test_import_modes_reject_nested_loss_without_outputs(
    legacy_source, tmp_path, caplog
):
    caplog.set_level(logging.ERROR)
    source, importer, state, now, _ = legacy_source
    vehicles = copy.deepcopy(state["vehicles"])
    vehicles[0]["location_snapshot"]["company"]["unknown"] = "SECRET-VALUE"
    update_legacy(source, "user:a:vehicles", vehicles)
    before = source.read_bytes()
    target = tmp_path / "never-created.db"
    for operation in (
        lambda: importer.inspect(now),
        lambda: importer.import_to(target, now),
    ):
        with pytest.raises(
            PersistenceError, match="vehicle.location_snapshot.company"
        ) as failure:
            operation()
        assert "SECRET-VALUE" not in str(failure.value)
        assert source.read_bytes() == before
        assert not target.exists()
    assert "SECRET-VALUE" not in caplog.text
    events = [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "state.import_rejected"
    ]
    assert events[-1].data["field_path"] == "vehicle.location_snapshot.company"


def test_nested_source_and_good_reject_wrong_leaf_shapes():
    for source in ({}, {**SOURCE, "url": {}}, {**SOURCE, "verified_at": []}):
        with pytest.raises(LegacyFieldError, match="source"):
            read_legacy_source(source, "source")
    for good in ({}, {**GOOD, "description": []}, {**GOOD, "cargo_code": {}}):
        with pytest.raises(LegacyFieldError, match="good"):
            read_legacy_good(good, "good")
    assert (
        read_legacy_good({**GOOD, "cargo_code": None}, "good").cargo_code
        is None
    )


def test_import_rejects_consistently_moved_vehicle_with_active_origin(
    legacy_source, tmp_path
):
    source, importer, state, now, _ = legacy_source
    vehicles = copy.deepcopy(state["vehicles"])
    destination = copy.deepcopy(state["contracts"][0]["destination"])
    vehicles[0].update(
        facility_uid=destination["facility_uid"],
        hub_id=destination["facility_uid"],
        location_snapshot=destination,
        hub=copy.deepcopy(destination),
    )
    update_legacy(source, "user:a:vehicles", vehicles)
    before = source.read_bytes()
    target = tmp_path / "invalid-location.db"
    with pytest.raises(PersistenceError) as failure:
        importer.import_to(target, now)
    assert (
        str(failure.value.__cause__)
        == "Travelling vehicle has changed location."
    )
    assert source.read_bytes() == before
    assert not target.exists()
