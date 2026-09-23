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
class CompanyIdentity:
    """Compact immutable company identity for runtime projections."""

    company_uid: str
    legal_name: str
    display_name: str
    country: str


@dataclass(frozen=True, slots=True)
class CargoProfile:
    """One NHM facility behavior profile with explicit evidence quality."""

    nhm_row_id: int
    code: str
    name: str
    role: str
    evidence_type: str
    confidence: float
    priority_score: float
    ancestor_row_ids: tuple[int, ...]
    source: SourceReference | None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CargoProfile:
        """Hydrate persisted NHM evidence for a contract offer."""
        raw_source = value.get("source")
        source = (
            SourceReference(
                url=str(raw_source["url"]),
                role=str(raw_source["role"]),
                verified_at=raw_source.get("verified_at"),
                precision=raw_source.get("precision"),
                provider=raw_source.get("provider"),
            )
            if isinstance(raw_source, dict)
            else None
        )
        return cls(
            nhm_row_id=int(value["nhm_row_id"]),
            code=str(value["code"]),
            name=str(value["name"]),
            role=str(value["role"]),
            evidence_type=str(value["evidence_type"]),
            confidence=float(value["confidence"]),
            priority_score=float(value["priority_score"]),
            ancestor_row_ids=tuple(value["ancestor_row_ids"]),
            source=source,
        )

    def is_compatible_with(self, other: CargoProfile) -> bool:
        """Match equal NHM nodes or profiles on the same ancestor chain."""
        return (
            self.nhm_row_id in other.ancestor_row_ids
            or other.nhm_row_id in self.ancestor_row_ids
        )


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
    city: str
    country: str
    address: str
    lat: float | None
    lon: float | None
    geocoding_status: str
    coordinate_evidence: tuple[SourceReference, ...]
    catalogue_version: str
    aliases: tuple[str, ...]
    resolution_status: str
    location_verified: bool
    snapshot_version: int = 1
    location_kind: str = "public_facility"

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> FacilityLocationSnapshot:
        """Hydrate a persisted compact or legacy-compatible snapshot."""
        raw_company = value.get("company")
        company = (
            CompanyIdentity(
                company_uid=str(raw_company["company_uid"]),
                legal_name=str(raw_company["legal_name"]),
                display_name=str(raw_company["display_name"]),
                country=str(raw_company["country"]),
            )
            if isinstance(raw_company, dict)
            else None
        )
        evidence = tuple(
            SourceReference(
                url=str(item["url"]),
                role=str(item["role"]),
                verified_at=item.get("verified_at"),
                precision=item.get("precision"),
                provider=item.get("provider"),
            )
            for item in value.get("coordinate_evidence", [])
        )
        return cls(
            facility_uid=str(value.get("facility_uid") or value["id"]),
            company=company,
            label=str(value["label"]),
            facility_type=str(value.get("facility_type", "")),
            city=str(value["city"]),
            country=str(value["country"]),
            address=str(value["address"]),
            lat=value.get("lat"),
            lon=value.get("lon"),
            geocoding_status=str(value.get("geocoding_status", "")),
            coordinate_evidence=evidence,
            catalogue_version=str(value.get("catalogue_version", "")),
            aliases=tuple(value.get("aliases", ())),
            resolution_status=str(
                value.get("resolution_status", "unavailable")
            ),
            location_verified=bool(value.get("location_verified", False)),
            snapshot_version=int(value.get("snapshot_version", 1)),
            location_kind=str(value.get("location_kind", "public_facility")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the compact snapshot at an external boundary."""
        return {
            "facility_uid": self.facility_uid,
            "id": self.facility_uid,
            "company_uid": (
                self.company.company_uid if self.company else None
            ),
            "company": asdict(self.company) if self.company else None,
            "label": self.label,
            "facility_type": self.facility_type,
            "city": self.city,
            "country": self.country,
            "address": self.address,
            "lat": self.lat,
            "lon": self.lon,
            "geocoding_status": self.geocoding_status,
            "coordinate_evidence": [
                asdict(item) for item in self.coordinate_evidence
            ],
            "catalogue_version": self.catalogue_version,
            "aliases": list(self.aliases),
            "resolution_status": self.resolution_status,
            "location_verified": self.location_verified,
            "snapshot_version": self.snapshot_version,
            "location_kind": self.location_kind,
        }


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
    cargo: tuple[CargoProfile, ...]
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
        if (
            self.lat is None
            or self.lon is None
            or not math.isfinite(self.lat)
            or not math.isfinite(self.lon)
            or not -90 <= self.lat <= 90
            or not -180 <= self.lon <= 180
        ):
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

    def inbound_cargo(self) -> tuple[CargoProfile, ...]:
        """Return NHM profiles that can receive or transship cargo."""
        return tuple(
            item for item in self.cargo if item.role in {"input", "both"}
        )

    def outbound_cargo(self) -> tuple[CargoProfile, ...]:
        """Return NHM profiles that can source or transship cargo."""
        return tuple(
            item for item in self.cargo if item.role in {"output", "both"}
        )

    def location_snapshot(self) -> FacilityLocationSnapshot:
        """Project typed routing and display facts needed at runtime."""
        company = (
            CompanyIdentity(
                company_uid=self.company.company_uid,
                legal_name=self.company.legal_name,
                display_name=self.company.display_name,
                country=self.company.country,
            )
            if self.company
            else None
        )
        return FacilityLocationSnapshot(
            facility_uid=self.facility_uid,
            company=company,
            label=self.label,
            facility_type=self.facility_type,
            city=self.city,
            country=self.country,
            address=self.address,
            lat=self.lat,
            lon=self.lon,
            geocoding_status=self.geocoding_status,
            coordinate_evidence=self.coordinate_evidence,
            catalogue_version=self.catalogue_version,
            aliases=self.aliases,
            resolution_status=(
                "resolved" if self.is_routable() else "unavailable"
            ),
            location_verified=self.has_verified_location(),
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
            "location_verified": self.has_verified_location(),
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
