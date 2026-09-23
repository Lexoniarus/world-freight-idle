"""Immutable real-world reference models, independent of simulation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.cargo import DocumentedCargo, FacilityNhmProfile
from app.domain.evidence import SourceReference
from app.domain.geography import Address, City, Coordinates, Country


@dataclass(frozen=True, slots=True)
class Company:
    """A reference company, never a player-owned business."""

    company_uid: str
    legal_name: str
    display_name: str
    country: Country
    website: str | None
    sources: tuple[SourceReference, ...]


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    """Compact immutable company identity for runtime projections."""

    company_uid: str
    legal_name: str | None
    display_name: str | None
    country: Country | None
    website: str | None = None
    sources: tuple[SourceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentedGood:
    """Exact handling description retained with the source document."""

    description: str
    cargo_code: str | None
    source: SourceReference


@dataclass(frozen=True, slots=True)
class FacilityLocationSnapshot:
    """Compact immutable routing and display projection."""

    facility_uid: str
    company: CompanyIdentity | None
    label: str
    facility_type: str
    city: City
    address: str
    coordinates: Coordinates | None
    geocoding_status: str
    coordinate_evidence: tuple[SourceReference, ...]
    catalogue_version: str
    aliases: tuple[str, ...]
    resolution_status: str
    location_verified: bool
    snapshot_version: int = 1
    location_kind: str = "public_facility"
    sources: tuple[SourceReference, ...] = ()
    handled_goods: tuple[DocumentedGood, ...] = ()
    handling_evidence: tuple[FacilityNhmProfile | DocumentedCargo, ...] = ()


@dataclass(frozen=True, slots=True)
class Facility:
    """Public freight endpoint with immutable evidence and stable identity."""

    facility_uid: str
    company: Company | None
    label: str
    facility_type: str
    address: Address
    coordinates: Coordinates | None
    geocoding_status: str
    sources: tuple[SourceReference, ...]
    coordinate_evidence: tuple[SourceReference, ...]
    nhm_profiles: tuple[FacilityNhmProfile, ...]
    catalogue_version: str
    aliases: tuple[str, ...] = ()
    handled_goods: tuple[DocumentedGood, ...] = ()

    def is_routable(self) -> bool:
        """Allow verified coordinates or explicit simulation estimates."""
        if self.geocoding_status not in {
            "verified_coordinates",
            "estimated_for_simulation",
        }:
            return False
        if self.coordinates is None:
            return False
        public_evidence = any(
            item.url.startswith(("https://", "http://"))
            for item in self.coordinate_evidence
        )
        simulation_evidence = any(
            item.url.startswith("internal://simulation-")
            for item in self.coordinate_evidence
        )
        if self.geocoding_status == "verified_coordinates":
            return public_evidence
        return public_evidence or simulation_evidence

    def has_verified_location(self) -> bool:
        """Report whether a routable location is independently verified."""
        return (
            self.geocoding_status == "verified_coordinates"
            and self.is_routable()
        )

    def inbound_profiles(self) -> tuple[FacilityNhmProfile, ...]:
        """Return NHM profiles that can receive or transship cargo."""
        return tuple(
            item
            for item in self.nhm_profiles
            if item.role in {"input", "both"}
        )

    def outbound_profiles(self) -> tuple[FacilityNhmProfile, ...]:
        """Return NHM profiles that can source or transship cargo."""
        return tuple(
            item
            for item in self.nhm_profiles
            if item.role in {"output", "both"}
        )

    def location_snapshot(self) -> FacilityLocationSnapshot:
        """Project typed routing and display facts needed at runtime."""
        company = (
            CompanyIdentity(
                company_uid=self.company.company_uid,
                legal_name=self.company.legal_name,
                display_name=self.company.display_name,
                country=self.company.country,
                website=self.company.website,
                sources=self.company.sources,
            )
            if self.company
            else None
        )
        return FacilityLocationSnapshot(
            facility_uid=self.facility_uid,
            company=company,
            label=self.label,
            facility_type=self.facility_type,
            city=self.address.city,
            address=self.address.display_text(),
            coordinates=self.coordinates,
            geocoding_status=self.geocoding_status,
            coordinate_evidence=self.coordinate_evidence,
            catalogue_version=self.catalogue_version,
            aliases=self.aliases,
            resolution_status=(
                "resolved" if self.is_routable() else "unavailable"
            ),
            location_verified=self.has_verified_location(),
            sources=self.sources,
            handled_goods=self.handled_goods,
        )


@dataclass(frozen=True, slots=True)
class FacilityQuery:
    """Map bounds; west greater than east crosses the antimeridian."""

    bbox: tuple[float, float, float, float] | None = None

    @classmethod
    def parse(cls, value: str | None) -> FacilityQuery:
        """Parse finite WGS84 bounds without silently clipping coordinates."""
        if value is None:
            return cls()
        parts = tuple(float(item) for item in value.split(","))
        if len(parts) != 4 or not all(math.isfinite(x) for x in parts):
            raise ValueError("Invalid bounding box")
        west, south, east, north = parts
        if not (
            -180 <= west <= 180
            and -180 <= east <= 180
            and -90 <= south <= north <= 90
        ):
            raise ValueError("Invalid bounding box")
        return cls((west, south, east, north))

    def includes(self, facility: Facility) -> bool:
        """Filter only routable facilities, including across world copies."""
        if not facility.is_routable():
            return False
        if self.bbox is None:
            return True
        west, south, east, north = self.bbox
        assert facility.coordinates is not None
        coordinates = facility.coordinates
        longitude = (
            west <= coordinates.longitude <= east
            if west <= east
            else coordinates.longitude >= west or coordinates.longitude <= east
        )
        return south <= coordinates.latitude <= north and longitude


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """One consistent catalogue read, with no live database handles."""

    version: str
    companies: tuple[Company, ...]
    facilities: tuple[Facility, ...]
    countries: tuple[Country, ...]
    cities: tuple[City, ...]
