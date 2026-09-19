"""Immutable real-world reference models, independent of simulation."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Evidence retained with a reference fact."""

    url: str
    role: str
    verified_at: str | None
    precision: str | None = None
    provider: str | None = None


@dataclass(frozen=True, slots=True)
class Company:
    """A reference company, never a player-owned business."""

    company_uid: str
    legal_name: str
    display_name: str
    country: str
    website: str | None
    sources: tuple[SourceReference, ...]


@dataclass(frozen=True, slots=True)
class DocumentedCargo:
    """A documented outward or handled good, without simulated economics."""

    code: str
    name: str
    role: str
    standard: bool
    evidence_type: str
    source: SourceReference


@dataclass(frozen=True, slots=True)
class DocumentedGood:
    """Exact handling description retained with the source document."""

    description: str
    cargo_code: str | None
    source: SourceReference


@dataclass(frozen=True, slots=True)
class Facility:
    """Public freight endpoint with immutable evidence and stable identity."""

    facility_uid: str
    company: Company | None
    label: str
    facility_type: str
    city: str
    country: str
    address: str
    lat: float | None
    lon: float | None
    geocoding_status: str
    sources: tuple[SourceReference, ...]
    coordinate_evidence: tuple[SourceReference, ...]
    cargo: tuple[DocumentedCargo, ...]
    catalogue_version: str
    aliases: tuple[str, ...] = ()
    handled_goods: tuple[DocumentedGood, ...] = ()

    def is_routable(self) -> bool:
        """Require facility-level coordinate evidence, never city guesses."""
        return (
            self.geocoding_status == "verified_coordinates"
            and self.lat is not None
            and self.lon is not None
            and math.isfinite(self.lat)
            and math.isfinite(self.lon)
            and -90 <= self.lat <= 90
            and -180 <= self.lon <= 180
            and bool(self.coordinate_evidence)
        )

    def outbound_cargo(self) -> tuple[DocumentedCargo, ...]:
        """Select evidenced standard goods suitable for simulated trucking."""
        return tuple(
            item
            for item in self.cargo
            if item.standard
            and item.role in {"output", "both"}
            and item.evidence_type in {"official", "osm", "statistical"}
        )

    def to_dict(self) -> dict[str, Any]:
        """Make an independent full endpoint snapshot and legacy projection."""
        return {
            **asdict(self),
            "id": self.facility_uid,
            "company_uid": self.company.company_uid if self.company else None,
            "resolution_status": (
                "resolved" if self.is_routable() else "unavailable"
            ),
            "snapshot_version": 1,
            "location_kind": "public_facility",
        }


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
        assert facility.lat is not None and facility.lon is not None
        longitude = (
            west <= facility.lon <= east
            if west <= east
            else facility.lon >= west or facility.lon <= east
        )
        return south <= facility.lat <= north and longitude


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    """One consistent catalogue read, with no live database handles."""

    version: str
    companies: tuple[Company, ...]
    facilities: tuple[Facility, ...]

    def get_facility(self, identifier: str) -> Facility:
        """Resolve a durable UID or explicitly maintained legacy alias."""
        matches = tuple(
            facility
            for facility in self.facilities
            if facility.facility_uid == identifier
            or identifier in facility.aliases
        )
        if len(matches) != 1:
            raise KeyError("Unknown or ambiguous facility")
        return matches[0]

    def get_company(self, company_uid: str) -> Company:
        """Resolve a reference company by its public stable UID."""
        for company in self.companies:
            if company.company_uid == company_uid:
                return company
        raise KeyError("Unknown company")

    def query(self, query: FacilityQuery) -> tuple[Facility, ...]:
        """Return stable-order map candidates without simulation state."""
        return tuple(f for f in self.facilities if query.includes(f))
