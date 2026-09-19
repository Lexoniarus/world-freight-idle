"""Validation for explicit catalogue maintenance, separate from SQL and CLI."""

import logging
import math
from typing import Any

from app.domain.ports import WorldMaintenanceStore

LOGGER = logging.getLogger(__name__)
LEGACY_ALIASES = frozenset(
    {
        "berlin_westhafen",
        "hamburg_cta",
        "duisburg_d3t",
        "rotterdam_maasvlakte",
    }
)


class WorldMaintenanceService:
    """Validate curated facts before delegating an atomic upgrade."""

    def __init__(self, repository: WorldMaintenanceStore) -> None:
        self.repository = repository

    def prepare(self, entries: list[dict[str, Any]]) -> None:
        """Require reviewed evidence for every legacy endpoint."""
        if (
            len(entries) != 4
            or {e["alias"] for e in entries} != LEGACY_ALIASES
        ):
            raise ValueError("Exactly four distinct legacy endpoints required")
        for entry in entries:
            validate_legacy_evidence(entry)
        self.repository.upgrade(entries)
        LOGGER.info(
            "World catalogue prepared",
            extra={
                "event": "world.prepared",
                "data": {"schema_version": "3.0.0"},
            },
        )


def validate_legacy_evidence(entry: dict[str, Any]) -> None:
    """Reject incomplete source claims and invalid coordinate candidates."""
    for key in (
        "company",
        "name",
        "city",
        "country",
        "verified_at",
        "goods",
        "provider",
    ):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise ValueError("Missing legacy source fact")
    for key in ("source_url", "coordinate_url"):
        if not entry[key].startswith("https://"):
            raise ValueError("Missing source URL")
    if entry["precision"] not in {
        "official_facility_coordinate",
        "facility_centroid",
        "osm_feature",
        "verified_address_point",
    }:
        raise ValueError("Unverified coordinate precision")
    for key, bound in (("lat", 90), ("lon", 180)):
        value = entry[key]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or abs(value) > bound
        ):
            raise ValueError("Invalid coordinate")
