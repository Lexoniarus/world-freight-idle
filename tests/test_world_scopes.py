"""Immutable world filters separate company identity from facility geography."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.domain.errors import AmbiguousWorldReference
from app.domain.geography import Address, City, Coordinates, Country
from app.domain.world import FacilityQuery
from app.domain.world_scopes import WorldScope


def test_world_scopes_filter_facilities_without_reparenting_companies(
    world_catalogue,
):
    snapshot = world_catalogue.read()
    berlin = WorldScope(snapshot).facility("berlin_westhafen")
    company = berlin.company
    assert company is not None
    germany = berlin.address.city.country
    france = Country("FR", "France")
    hamburg = WorldScope(snapshot).city("Hamburg").city
    paris = City("a0000000-0000-4000-8000-000000000001", "Paris", france)
    second = replace(
        berlin,
        facility_uid="second",
        address=Address(hamburg),
        aliases=(),
        coordinates=Coordinates(53.5, 10),
    )
    third = replace(
        berlin,
        facility_uid="third",
        address=Address(paris),
        aliases=(),
        coordinates=Coordinates(48.8, 2.3),
    )
    snapshot = replace(
        snapshot,
        facilities=(berlin, second, third),
        companies=(company,),
        countries=(germany, france),
        cities=(berlin.address.city, hamburg, paris),
    )
    world = WorldScope(snapshot)
    assert world.facilities == (berlin, second, third)
    assert world.company(company.company_uid).facilities == world.facilities
    german = world.country("de")
    assert german.facilities == (berlin, second)
    assert german.company(company.display_name).facilities == (berlin, second)
    assert german.city("berlin").company(company.legal_name).facilities == (
        berlin,
    )
    assert world.city(paris.city_uid).facilities == (third,)
    french = world.country("FR").company(company.company_uid)
    assert french.facilities == (third,)
    assert french.company is company and french.company.country is germany
    assert world.query(FacilityQuery((12, 52, 14, 54))) == (berlin,)
    assert world.query(FacilityQuery((-1, -1, 1, 1))) == ()
    assert WorldScope(replace(snapshot, facilities=())).facilities == ()
    for scope, field, value in (
        (world, "_world", snapshot),
        (german, "country", france),
        (german.city("Berlin"), "city", paris),
        (french, "company", company),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(scope, field, value)
    with pytest.raises(KeyError):
        german.city(paris.city_uid)
    with pytest.raises(KeyError):
        german.city("Berlin").company("missing")
    with pytest.raises(KeyError):
        german.company("missing")


def test_world_scopes_report_ambiguity_and_keep_uid_queries_exact(
    world_catalogue,
):
    snapshot = world_catalogue.read()
    berlin = WorldScope(snapshot).facility("berlin_westhafen")
    company = berlin.company
    assert company is not None
    city = berlin.address.city
    duplicate_city = replace(
        city, city_uid="a0000000-0000-4000-8000-000000000001", region="Other"
    )
    duplicate_company = replace(company, company_uid="other-company")
    duplicate_facility = replace(berlin, facility_uid="other-facility")
    germany = city.country
    other_country = Country("FR", germany.name)
    world = WorldScope(
        replace(
            snapshot,
            facilities=(berlin, duplicate_facility),
            companies=(company, duplicate_company),
            cities=(city, duplicate_city),
            countries=(germany, other_country),
        )
    )
    assert world.facility(berlin.facility_uid) is berlin
    assert world.country("DE").country is germany
    assert world.city(city.city_uid).city is city
    assert (
        world.country("DE").city(duplicate_city.city_uid).city
        is duplicate_city
    )
    assert world.company(company.company_uid).company is company
    for query in (
        lambda: world.facility("berlin_westhafen"),
        lambda: world.country(germany.name),
        lambda: world.city("Berlin"),
        lambda: world.country("DE").city("Berlin"),
        lambda: world.company(company.display_name),
    ):
        with pytest.raises(AmbiguousWorldReference):
            query()
    for query in (world.facility, world.country, world.city, world.company):
        with pytest.raises(KeyError):
            query("unknown")
