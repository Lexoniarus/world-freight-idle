"""World filters separate company identity from facility geography."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.domain.errors import AmbiguousWorldReference
from app.domain.evidence import SourceReference
from app.domain.geography import Address, City, Coordinates, Country
from app.domain.world import FacilityQuery
from app.domain.world_scopes import WorldScope


def test_world_scopes_filter_facilities_without_reparenting_companies(
    synthetic_world_catalogue,
):
    snapshot = synthetic_world_catalogue.read()
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
    synthetic_world_catalogue,
):
    snapshot = synthetic_world_catalogue.read()
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


def test_facility_rules_preserve_immutable_location_snapshots(
    synthetic_world_catalogue,
):
    world = synthetic_world_catalogue.read()
    berlin = WorldScope(world).facility("berlin_westhafen")
    verified = replace(
        berlin,
        geocoding_status="verified_coordinates",
        coordinate_evidence=(
            SourceReference(
                "https://example.test/coordinates",
                "verified test coordinates",
                None,
            ),
        ),
    )
    assert verified.is_routable()
    assert verified.has_verified_location()
    assert berlin.outbound_profiles()
    bidirectional = world.facilities[2]
    assert bidirectional.outbound_profiles()
    assert bidirectional.inbound_profiles()

    location = verified.location_snapshot()
    assert location.facility_uid == berlin.facility_uid
    assert location.coordinate_evidence
    assert location.company is not None
    assert berlin.company is not None
    assert location.company.company_uid == berlin.company.company_uid
    with pytest.raises(FrozenInstanceError):
        setattr(location, "label", "changed")

    for field, value in (
        ("coordinates", None),
        ("coordinate_evidence", ()),
        ("geocoding_status", "candidate"),
    ):
        assert not replace(verified, **{field: value}).is_routable()

    outbound = bidirectional.outbound_profiles()[0]
    assert not replace(
        bidirectional,
        nhm_profiles=(replace(outbound, role="input"),),
    ).outbound_profiles()
    inbound = bidirectional.inbound_profiles()[0]
    assert not replace(
        bidirectional,
        nhm_profiles=(replace(inbound, role="output"),),
    ).inbound_profiles()


def test_facility_query_parses_bounds_and_wraps_the_dateline(
    synthetic_world_catalogue,
):
    berlin = WorldScope(synthetic_world_catalogue.read()).facility(
        "berlin_westhafen"
    )
    assert not FacilityQuery().includes(replace(berlin, coordinates=None))
    dateline = FacilityQuery.parse("170,-10,-170,10")
    assert dateline.includes(replace(berlin, coordinates=Coordinates(0, 179)))
    assert dateline.includes(replace(berlin, coordinates=Coordinates(0, -179)))
    assert not dateline.includes(
        replace(berlin, coordinates=Coordinates(0, 0))
    )
    assert FacilityQuery.parse("13,52,14,53").includes(berlin)
    assert not FacilityQuery.parse("0,0,1,1").includes(berlin)
    for bounds in ("", "0,1,2", "nan,0,1,2", "181,0,1,2", "0,4,1,2"):
        with pytest.raises(ValueError):
            FacilityQuery.parse(bounds)
