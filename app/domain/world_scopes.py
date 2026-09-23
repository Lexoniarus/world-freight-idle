"""Immutable geographical views; companies stay independent of any city."""

from dataclasses import dataclass
from typing import TypeVar

from app.domain.errors import AmbiguousWorldReference
from app.domain.geography import City, Country
from app.domain.world import Company, Facility, FacilityQuery, WorldSnapshot

Reference = TypeVar("Reference")


def require_unique_reference(
    matches: tuple[Reference, ...], kind: str
) -> Reference:
    """Distinguish missing identities from ambiguous names explicitly."""
    if not matches:
        raise KeyError(f"Unknown {kind}")
    if len(matches) != 1:
        raise AmbiguousWorldReference(f"Ambiguous {kind}; use its UID.")
    return matches[0]


def select_city(cities: tuple[City, ...], identifier: str) -> City:
    """Prefer a durable city UID; accept names only when unambiguous."""
    identities = tuple(c for c in cities if c.city_uid == identifier)
    names = tuple(
        c for c in cities if c.name.casefold() == identifier.casefold()
    )
    return require_unique_reference(identities or names, "city")


def select_company(companies: tuple[Company, ...], identifier: str) -> Company:
    """Resolve a company UID or an unambiguous legal/display name."""
    identities = tuple(c for c in companies if c.company_uid == identifier)
    names = tuple(
        c
        for c in companies
        if identifier.casefold()
        in {
            c.legal_name.casefold(),
            c.display_name.casefold(),
        }
    )
    return require_unique_reference(identities or names, "company")


def scope_company(
    facilities: tuple[Facility, ...], identifier: str
) -> "CompanyScope":
    """Select a company through geographically filtered facilities."""
    companies = {
        facility.company.company_uid: facility.company
        for facility in facilities
        if facility.company is not None
    }
    company = select_company(tuple(companies.values()), identifier)
    return CompanyScope(
        company,
        tuple(
            f
            for f in facilities
            if f.company and f.company.company_uid == company.company_uid
        ),
    )


@dataclass(frozen=True, slots=True)
class WorldScope:
    """Query one consistent reference revision without database access."""

    _world: WorldSnapshot

    @property
    def facilities(self) -> tuple[Facility, ...]:
        """Expose the immutable facilities of this reference revision."""
        return self._world.facilities

    def facility(self, identifier: str) -> Facility:
        """Resolve a facility UID or its explicitly maintained legacy alias."""
        identities = tuple(
            f for f in self.facilities if f.facility_uid == identifier
        )
        aliases = tuple(f for f in self.facilities if identifier in f.aliases)
        return require_unique_reference(identities or aliases, "facility")

    def country(self, identifier: str) -> "CountryScope":
        """Select a country by code or an unambiguous display name."""
        identities = tuple(
            c for c in self._world.countries if c.code == identifier.upper()
        )
        names = tuple(
            c
            for c in self._world.countries
            if c.name.casefold() == identifier.casefold()
        )
        return CountryScope(
            self._world,
            require_unique_reference(identities or names, "country"),
        )

    def city(self, identifier: str) -> "CityScope":
        """Select a city globally; a shared name requires further scoping."""
        return CityScope(
            self._world, select_city(self._world.cities, identifier)
        )

    def company(self, identifier: str) -> "CompanyScope":
        """Select a reference company without implying ownership by a city."""
        company = select_company(self._world.companies, identifier)
        return CompanyScope(
            company,
            tuple(
                f
                for f in self.facilities
                if f.company and f.company.company_uid == company.company_uid
            ),
        )

    def query(self, query: FacilityQuery) -> tuple[Facility, ...]:
        """Apply map bounds while retaining stable facility order."""
        return tuple(f for f in self.facilities if query.includes(f))


@dataclass(frozen=True, slots=True)
class CountryScope:
    """Facility view constrained by the country of each facility's city."""

    _world: WorldSnapshot
    country: Country

    @property
    def facilities(self) -> tuple[Facility, ...]:
        """Return facilities physically located inside this country."""
        return tuple(
            f
            for f in self._world.facilities
            if f.address.city.country.code == self.country.code
        )

    def city(self, identifier: str) -> "CityScope":
        """Resolve a city only among cities belonging to this country."""
        cities = tuple(
            c
            for c in self._world.cities
            if c.country.code == self.country.code
        )
        return CityScope(self._world, select_city(cities, identifier))

    def company(self, identifier: str) -> "CompanyScope":
        """Filter a company's facilities without changing its legal country."""
        return scope_company(self.facilities, identifier)


@dataclass(frozen=True, slots=True)
class CityScope:
    """Facility view constrained by a durable city identity."""

    _world: WorldSnapshot
    city: City

    @property
    def facilities(self) -> tuple[Facility, ...]:
        """Return facilities in this city without name-based conflation."""
        return tuple(
            f
            for f in self._world.facilities
            if f.address.city.city_uid == self.city.city_uid
        )

    def company(self, identifier: str) -> "CompanyScope":
        """Select a company through its facilities in this city."""
        return scope_company(self.facilities, identifier)


@dataclass(frozen=True, slots=True)
class CompanyScope:
    """One company and only its facilities matching the preceding filters."""

    company: Company
    facilities: tuple[Facility, ...]
