"""Public facility fields projected from historical location values."""

from dataclasses import asdict
from typing import Any

from app.domain.world import FacilityLocationSnapshot


def project_location(location: FacilityLocationSnapshot) -> dict[str, Any]:
    """Expose facility identity and provenance without reference expansion."""
    return {
        "facility_uid": location.facility_uid,
        "id": location.facility_uid,
        "company_uid": (
            location.company.company_uid if location.company else None
        ),
        "company": asdict(location.company) if location.company else None,
        "label": location.label,
        "facility_type": location.facility_type,
        "city": location.city,
        "country": location.country,
        "address": location.address,
        "lat": location.lat,
        "lon": location.lon,
        "geocoding_status": location.geocoding_status,
        "coordinate_evidence": [
            asdict(item) for item in location.coordinate_evidence
        ],
        "catalogue_version": location.catalogue_version,
        "aliases": list(location.aliases),
        "resolution_status": location.resolution_status,
        "location_verified": location.location_verified,
        "snapshot_version": location.snapshot_version,
        "location_kind": location.location_kind,
    }
