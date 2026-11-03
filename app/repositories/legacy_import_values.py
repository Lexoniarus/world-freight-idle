"""Strict decoders for nested values in legacy snapshot documents."""

from dataclasses import fields
from typing import Any

from app.domain.cargo import DocumentedCargo, FacilityNhmProfile, NhmProduct
from app.domain.evidence import SourceReference
from app.domain.world import DocumentedGood


class LegacyFieldError(ValueError):
    """Identify a rejected document path without carrying its field values."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Invalid legacy fields at {path}.")


def read_legacy_profile(
    value: dict[str, Any], path: str = "cargo"
) -> FacilityNhmProfile:
    """Separate the saved product hierarchy from saved handling evidence."""
    reject_unknown_fields(value, NHM_PROFILE_FIELDS, path)
    return FacilityNhmProfile(
        product=NhmProduct(
            value["nhm_row_id"],
            value["code"],
            value["name"],
            tuple(
                require_legacy_array(
                    value["ancestor_row_ids"], path + ".ancestor_row_ids"
                )
            ),
        ),
        role=value["role"],
        evidence_type=value["evidence_type"],
        confidence=value["confidence"],
        priority_score=value["priority_score"],
        source=read_legacy_source(value["source"], path + ".source")
        if value["source"] is not None
        else None,
    )


LOCATION_FIELDS = frozenset(
    {
        "facility_uid",
        "id",
        "company_uid",
        "company",
        "label",
        "facility_type",
        "city",
        "city_uid",
        "country",
        "address",
        "lat",
        "lon",
        "geocoding_status",
        "coordinate_evidence",
        "catalogue_version",
        "aliases",
        "resolution_status",
        "location_verified",
        "snapshot_version",
        "location_kind",
        "sources",
        "handled_goods",
        "cargo",
    }
)
VEHICLE_FIELDS = frozenset(
    {
        "id",
        "name",
        "mode",
        "capacity_tons",
        "hub_id",
        "status",
        "model_id",
        "operating_cost_eur_per_km",
        "facility_uid",
        "location_snapshot",
        "hub",
    }
)
OFFER_FIELDS = frozenset(
    {
        "id",
        "market_model",
        "cargo_system",
        "origin_hub_id",
        "destination_hub_id",
        "origin_facility_uid",
        "destination_facility_uid",
        "origin",
        "destination",
        "shipper_name",
        "consignee_name",
        "cargo",
        "cargo_code",
        "cargo_evidence",
        "origin_cargo_evidence",
        "destination_cargo_evidence",
        "cargo_basis",
        "trade_match_type",
        "tons",
        "payload_band",
        "rate_eur_per_km_ton",
        "created_at",
        "expires_at",
        "mode",
        "relationship_simulated",
    }
)
TRANSPORT_FIELDS = frozenset(
    {
        "id",
        "vehicle_id",
        "contract",
        "origin",
        "destination",
        "origin_snapshot",
        "destination_snapshot",
        "route_geojson",
        "distance_km",
        "routing_duration_seconds",
        "provider",
        "departed_at",
        "arrives_at",
        "payout_eur",
        "operating_cost_eur",
        "profit_eur",
        "status",
        "settled_at",
    }
)


def reject_unknown_fields(
    value: dict[str, Any], allowed: frozenset[str], path: str = "snapshot"
) -> None:
    """Fail closed on unrecognized documents rather than losing new fields."""
    if not isinstance(value, dict) or value.keys() - allowed:
        raise LegacyFieldError(path)


def read_documented_cargo(
    value: dict[str, Any], path: str = "cargo"
) -> DocumentedCargo:
    """Retain an older documented classification as its own historical fact."""
    reject_unknown_fields(value, DOCUMENTED_CARGO_FIELDS, path)
    return DocumentedCargo(
        **{
            **value,
            "source": read_legacy_source(value["source"], path + ".source")
            if value["source"] is not None
            else None,
        }
    )


COMPANY_FIELDS = frozenset(
    {
        "company_uid",
        "legal_name",
        "display_name",
        "country",
        "website",
        "sources",
    }
)
SOURCE_FIELDS = frozenset(field.name for field in fields(SourceReference))
GOOD_FIELDS = frozenset(field.name for field in fields(DocumentedGood))
DOCUMENTED_CARGO_FIELDS = frozenset(
    field.name for field in fields(DocumentedCargo)
)
NHM_PROFILE_FIELDS = frozenset(
    {
        "nhm_row_id",
        "code",
        "name",
        "ancestor_row_ids",
        "role",
        "evidence_type",
        "confidence",
        "priority_score",
        "source",
    }
)


def require_legacy_array(value: object, path: str) -> list[Any]:
    """Reject non-array containers before visiting historical children."""
    if not isinstance(value, list):
        raise LegacyFieldError(path)
    return value


def read_legacy_source(value: dict[str, Any], path: str) -> SourceReference:
    """Retain known source metadata and reject unrecognized evidence."""
    reject_unknown_fields(value, SOURCE_FIELDS, path)
    if not {"url", "role", "verified_at"} <= value.keys():
        raise LegacyFieldError(path)
    for name in SOURCE_FIELDS:
        item = value.get(name)
        if not isinstance(item, str) and (
            item is not None or name in {"url", "role"}
        ):
            raise LegacyFieldError(path + "." + name)
    return SourceReference(**value)


def read_legacy_sources(
    value: object, path: str
) -> tuple[SourceReference, ...]:
    """Decode an explicit source array with indexed diagnostic paths."""
    return tuple(
        read_legacy_source(item, f"{path}[{index}]")
        for index, item in enumerate(require_legacy_array(value, path))
    )


def read_legacy_good(value: dict[str, Any], path: str) -> DocumentedGood:
    """Preserve a documented goods description and its complete evidence."""
    reject_unknown_fields(value, GOOD_FIELDS, path)
    if not GOOD_FIELDS <= value.keys():
        raise LegacyFieldError(path)
    if not isinstance(value["description"], str):
        raise LegacyFieldError(path + ".description")
    if value["cargo_code"] is not None and not isinstance(
        value["cargo_code"], str
    ):
        raise LegacyFieldError(path + ".cargo_code")
    return DocumentedGood(
        **{
            **value,
            "source": read_legacy_source(value["source"], path + ".source"),
        }
    )


def read_legacy_route(
    value: dict[str, Any], path: str
) -> tuple[tuple[float, float], ...]:
    """Read supported GeoJSON without silently discarding feature metadata."""
    reject_unknown_fields(
        value,
        frozenset({"type", "geometry", "properties", "coordinates"}),
        path,
    )
    if value.get("type") == "Feature":
        reject_unknown_fields(
            value, frozenset({"type", "geometry", "properties"}), path
        )
        if value.get("properties") is not None:
            reject_unknown_fields(
                value["properties"], frozenset(), path + ".properties"
            )
        value = value["geometry"]
        path += ".geometry"
    reject_unknown_fields(value, frozenset({"type", "coordinates"}), path)
    if value.get("type") != "LineString":
        raise LegacyFieldError(path + ".type")
    coordinates = []
    for index, point in enumerate(
        require_legacy_array(value["coordinates"], path + ".coordinates")
    ):
        pair = require_legacy_array(point, f"{path}.coordinates[{index}]")
        if len(pair) != 2:
            raise LegacyFieldError(f"{path}.coordinates[{index}]")
        coordinates.append((pair[0], pair[1]))
    return tuple(coordinates)
