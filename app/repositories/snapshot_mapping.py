"""Decode canonical historical values owned by the SQLite repository."""

from typing import Any

from app.domain.contracts import ContractOffer
from app.domain.world import (
    CargoProfile,
    CompanyIdentity,
    FacilityLocationSnapshot,
    SourceReference,
)


def load_location(value: dict[str, Any]) -> FacilityLocationSnapshot:
    """Restore a complete location without aliases or catalogue lookups."""
    return FacilityLocationSnapshot(
        **{
            **value,
            "company": (
                CompanyIdentity(**value["company"])
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


def load_cargo(value: dict[str, Any]) -> CargoProfile:
    """Restore one saved NHM profile including its original evidence."""
    return CargoProfile(
        **{
            **value,
            "ancestor_row_ids": tuple(value["ancestor_row_ids"]),
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
            "cargo": load_cargo(value["cargo"]),
            "origin_cargo_evidence": load_cargo(
                value["origin_cargo_evidence"]
            ),
            "destination_cargo_evidence": load_cargo(
                value["destination_cargo_evidence"]
            ),
        }
    )
