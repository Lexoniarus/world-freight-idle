"""Reviewed identities required by the explicit reference-world upgrade."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.geography import City, Country


@dataclass(frozen=True, slots=True)
class FacilityCityAssignment:
    """Explicit facility assignment with its expected source geography."""

    facility_uid: str
    city_uid: str
    source_country: str
    source_city: str
    source_region: str | None


@dataclass(frozen=True, slots=True)
class GeographyMapping:
    """One reviewed manifest revision, independent of SQLite row numbers."""

    version: int
    source_data_version: str
    countries: tuple[Country, ...]
    cities: tuple[City, ...]
    facilities: tuple[FacilityCityAssignment, ...]


class GeographyMigrationStore(Protocol):
    """Offline output boundary; runtime catalogues remain read-only."""

    def normalize(self, mapping: GeographyMapping) -> None:
        """Write or verify an already matching normalized catalogue."""
        ...
