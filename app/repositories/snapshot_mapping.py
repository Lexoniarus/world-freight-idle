"""Decode canonical historical values owned by the SQLite repository."""

from typing import Any

from app.domain.cargo import DocumentedCargo, FacilityNhmProfile, NhmProduct
from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.evidence import SourceReference
from app.domain.geography import City, Coordinates, Country
from app.domain.world import (
    CompanyIdentity,
    DocumentedGood,
    FacilityLocationSnapshot,
)


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
                        "country": Country(**value["company"]["country"])
                        if value["company"]["country"]
                        else None,
                        "sources": tuple(
                            SourceReference(**item)
                            for item in value["company"]["sources"]
                        ),
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
            "sources": tuple(
                SourceReference(**item) for item in value["sources"]
            ),
            "handled_goods": tuple(
                DocumentedGood(
                    **{**item, "source": SourceReference(**item["source"])}
                )
                for item in value["handled_goods"]
            ),
            "handling_evidence": tuple(
                load_profile(item)
                if "product" in item
                else load_documented_cargo(item)
                for item in value["handling_evidence"]
            ),
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


def load_documented_cargo(value: dict[str, Any]) -> DocumentedCargo:
    """Restore non-NHM historical evidence without a catalogue lookup."""
    return DocumentedCargo(
        **{
            **value,
            "source": SourceReference(**value["source"])
            if value["source"]
            else None,
        }
    )


def load_historical_contract(
    value: dict[str, Any],
) -> HistoricalContractSnapshot:
    """Restore agreed transport terms independently of offer availability."""
    return HistoricalContractSnapshot(
        **{
            **value,
            "origin": load_location(value["origin"]),
            "destination": load_location(value["destination"]),
            "cargo": load_product(value["cargo"])
            if "nhm_row_id" in value["cargo"]
            else load_documented_cargo(value["cargo"]),
            "origin_cargo_evidence": load_profile(
                value["origin_cargo_evidence"]
            )
            if value["origin_cargo_evidence"] is not None
            else None,
            "destination_cargo_evidence": load_profile(
                value["destination_cargo_evidence"]
            )
            if value["destination_cargo_evidence"] is not None
            else None,
        }
    )
