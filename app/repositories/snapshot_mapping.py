"""Decode canonical historical values owned by the SQLite repository."""

from typing import Any

from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.contracts import ContractOffer
from app.domain.evidence import SourceReference
from app.domain.geography import City, Coordinates, Country
from app.domain.world import CompanyIdentity, FacilityLocationSnapshot


def load_location(value: dict[str, Any]) -> FacilityLocationSnapshot:
    """Restore a complete location without aliases or catalogue lookups."""
    return FacilityLocationSnapshot(
        **{
            **value,
            "city": load_city(value["city"]),
            "coordinates": (
                Coordinates(**value["coordinates"])
                if value["coordinates"] is not None
                else None
            ),
            "company": (
                CompanyIdentity(
                    **{
                        **value["company"],
                        "country": Country(**value["company"]["country"]),
                    }
                )
                if value["company"] is not None
                else None
            ),
            "coordinate_evidence": tuple(
                SourceReference(**item)
                for item in value["coordinate_evidence"]
            ),
            "aliases": tuple(value["aliases"]),
        }
    )


def load_product(value: dict[str, Any]) -> NhmProduct:
    """Restore a saved product hierarchy independently of the catalogue."""
    return NhmProduct(
        **{**value, "ancestor_row_ids": tuple(value["ancestor_row_ids"])}
    )


def load_profile(value: dict[str, Any]) -> FacilityNhmProfile:
    """Restore facility-specific handling evidence for a historical product."""
    return FacilityNhmProfile(
        **{
            **value,
            "product": load_product(value["product"]),
            "source": (
                SourceReference(**value["source"])
                if value["source"] is not None
                else None
            ),
        }
    )


def load_offer(value: dict[str, Any]) -> ContractOffer:
    """Restore one complete offer using its retained reference facts."""
    return ContractOffer(
        **{
            **value,
            "origin": load_location(value["origin"]),
            "destination": load_location(value["destination"]),
            "cargo": load_product(value["cargo"]),
            "origin_cargo_evidence": load_profile(
                value["origin_cargo_evidence"]
            ),
            "destination_cargo_evidence": load_profile(
                value["destination_cargo_evidence"]
            ),
        }
    )


def load_city(value: dict[str, Any]) -> City:
    """Restore a historical city and country without current-catalogue IO."""
    return City(**{**value, "country": Country(**value["country"])})
