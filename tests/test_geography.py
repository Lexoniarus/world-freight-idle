"""Geographical value objects preserve identity and reject invalid values."""

from dataclasses import replace

import pytest

from app.domain.geography import Address, City, Coordinates, Country


def test_geography_values_reject_invalid_coordinates_and_identities():
    coordinates = Coordinates(-90, 180)
    assert coordinates.longitude == 180
    for changes in (
        {"latitude": 91},
        {"latitude": -91},
        {"longitude": 181},
        {"longitude": -181},
        {"latitude": True},
        {"longitude": float("nan")},
        {"latitude": float("inf")},
    ):
        with pytest.raises(ValueError):
            replace(coordinates, **changes)
    country = Country("DE", "Germany")
    for code in ("", "de", "DEU", "D1", "DÉ"):
        with pytest.raises(ValueError):
            replace(country, code=code)
    with pytest.raises(ValueError):
        replace(country, name="")
    city = City("a0000000-0000-4000-8000-000000000001", "Berlin", country)
    for changes in (
        {"city_uid": "12"},
        {"name": ""},
        {"region": ""},
        {"city_uid": city.city_uid.upper()},
    ):
        with pytest.raises(ValueError):
            replace(city, **changes)
    assert Address(city, "Street", "1", "10000").display_text() == (
        "Street, 1, 10000, Berlin, DE"
    )
    assert Address(city).display_text() == "Berlin, DE"
