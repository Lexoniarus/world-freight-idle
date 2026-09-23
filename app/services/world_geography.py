"""Validate explicit geographical assignments before reference migration."""

from typing import Any
from uuid import UUID

from app.domain.geography import City, Country
from app.domain.geography_migration import (
    FacilityCityAssignment,
    GeographyMapping,
)


def validate_geography_mapping(document: dict[str, Any]) -> GeographyMapping:
    """Reject incomplete, duplicate or conflicting reviewed identities."""
    if (
        type(document["version"]) is not int
        or document["version"] != 1
        or document["source_schema"] != "3.0.0"
        or not document["source_data_version"]
    ):
        raise ValueError("Unsupported geography mapping revision.")
    countries = tuple(Country(**item) for item in document["countries"])
    by_country = {country.code: country for country in countries}
    cities = tuple(
        City(
            item["city_uid"],
            item["name"],
            by_country[item["country_code"]],
            item["region"],
        )
        for item in document["cities"]
    )
    by_city = {city.city_uid: city for city in cities}
    assignments = tuple(
        FacilityCityAssignment(**item) for item in document["facilities"]
    )
    if (
        not countries
        or not cities
        or not assignments
        or len(countries) != len(by_country)
        or len(cities) != len(by_city)
        or len(assignments) != len({a.facility_uid for a in assignments})
    ):
        raise ValueError("Missing or duplicate geography identity.")
    for assignment in assignments:
        if str(UUID(assignment.facility_uid)) != assignment.facility_uid:
            raise ValueError("Invalid facility UID.")
        city = by_city[assignment.city_uid]
        if (
            city.country.code != assignment.source_country
            or city.name != assignment.source_city
            or assignment.source_region not in {None, city.region}
        ):
            raise ValueError("Conflicting facility geography assignment.")
    return GeographyMapping(
        document["version"],
        document["source_data_version"],
        countries,
        cities,
        assignments,
    )
