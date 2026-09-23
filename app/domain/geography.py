"""Immutable geographical identities and validated address values."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.validation import require_finite, require_identity


@dataclass(frozen=True, slots=True)
class Coordinates:
    """One finite WGS84 position, without a verification claim."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """Reject nonnumeric, nonfinite and out-of-range coordinates."""
        require_finite(self.latitude, "Latitude", -90)
        require_finite(self.longitude, "Longitude", -180)
        if self.latitude > 90 or self.longitude > 180:
            raise ValueError("Coordinates outside WGS84.")


@dataclass(frozen=True, slots=True)
class Country:
    """Reference country identified by its established two-letter code."""

    code: str
    name: str

    def __post_init__(self) -> None:
        """Require an uppercase country identity and a display name."""
        require_identity(self.code, "Country code")
        require_identity(self.name, "Country name")
        if len(self.code) != 2 or not self.code.isascii():
            raise ValueError("Invalid country code.")
        if not self.code.isalpha() or self.code != self.code.upper():
            raise ValueError("Invalid country code.")


@dataclass(frozen=True, slots=True)
class City:
    """Persisted city identity; a name is never an identity generator."""

    city_uid: str
    name: str
    country: Country
    region: str | None = None

    def __post_init__(self) -> None:
        """Require a canonical UUID and explicit city/country identity."""
        require_identity(self.city_uid, "City UID")
        require_identity(self.name, "City name")
        if str(UUID(self.city_uid)) != self.city_uid:
            raise ValueError("Invalid city UID.")
        if self.region is not None:
            require_identity(self.region, "Region")


@dataclass(frozen=True, slots=True)
class Address:
    """Address components belonging to one stable city reference."""

    city: City
    street: str | None = None
    house_number: str | None = None
    postal_code: str | None = None

    def display_text(self) -> str:
        """Format address text without duplicating geographical values."""
        return ", ".join(
            value
            for value in (
                self.street,
                self.house_number,
                self.postal_code,
                self.city.name,
                self.city.country.code,
            )
            if value
        )
