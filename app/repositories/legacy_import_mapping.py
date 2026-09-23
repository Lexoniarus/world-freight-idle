"""Strict, offline-only decoding of the former KV snapshot documents."""

from typing import Any

from app.domain.cargo import DocumentedCargo, FacilityNhmProfile, NhmProduct
from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.evidence import SourceReference
from app.domain.game import OwnedVehicle
from app.domain.geography import City, Coordinates
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.domain.validation import require_finite, require_identity
from app.domain.world import (
    CompanyIdentity,
    DocumentedGood,
    FacilityLocationSnapshot,
)
from app.domain.world_scopes import WorldScope


class LegacySnapshotReader:
    """Resolve new city identities while preserving saved historical facts."""

    def __init__(self, world: WorldScope) -> None:
        self.world = world

    def location(self, value: dict[str, Any]) -> FacilityLocationSnapshot:
        """Add the reviewed city UID, retaining old labels and coordinates."""
        reject_unknown_fields(value, LOCATION_FIELDS)
        if (
            value["snapshot_version"] != 1
            or value["location_kind"] != "public_facility"
        ):
            raise ValueError("Unknown location snapshot version or kind.")
        uid = value["facility_uid"]
        reference = self.world.facility(uid)
        if value.get("id", uid) != uid:
            raise ValueError("Conflicting historical facility identities.")
        country = self.world.country(value["country"]).country
        city = City(
            reference.address.city.city_uid,
            value["city"],
            country,
            reference.address.city.region,
        )
        raw_company = value.get("company")
        company = None
        if raw_company is not None:
            company = CompanyIdentity(
                raw_company["company_uid"],
                raw_company["legal_name"],
                raw_company["display_name"],
                self.world.country(raw_company["country"]).country,
                raw_company.get("website"),
                tuple(
                    SourceReference(**item)
                    for item in raw_company.get("sources", [])
                ),
            )
        elif value.get("company_uid"):
            company = CompanyIdentity(value["company_uid"], None, None, None)
        if value.get("company_uid") != (
            company.company_uid if company else None
        ):
            raise ValueError("Conflicting historical company identities.")
        if (value["lat"] is None) != (value["lon"] is None):
            raise ValueError("Incomplete historical coordinates.")
        return FacilityLocationSnapshot(
            facility_uid=uid,
            company=company,
            label=value["label"],
            facility_type=value["facility_type"],
            city=city,
            address=value["address"],
            coordinates=Coordinates(value["lat"], value["lon"])
            if value["lat"] is not None
            else None,
            geocoding_status=value["geocoding_status"],
            coordinate_evidence=tuple(
                SourceReference(**item)
                for item in value["coordinate_evidence"]
            ),
            catalogue_version=value["catalogue_version"],
            aliases=tuple(value["aliases"]),
            resolution_status=value["resolution_status"],
            location_verified=value.get(
                "location_verified",
                value["geocoding_status"] == "verified_coordinates",
            ),
            snapshot_version=value["snapshot_version"],
            location_kind=value["location_kind"],
            sources=tuple(
                SourceReference(**item) for item in value.get("sources", [])
            ),
            handled_goods=tuple(
                DocumentedGood(
                    **{**item, "source": SourceReference(**item["source"])}
                )
                for item in value.get("handled_goods", [])
            ),
            handling_evidence=tuple(
                read_legacy_profile(item)
                if "nhm_row_id" in item
                else read_documented_cargo(item)
                for item in value.get("cargo", [])
            ),
        )

    def vehicle(self, value: dict[str, Any]) -> OwnedVehicle:
        """Retain purchased values and resolve the former public hub alias."""
        reject_unknown_fields(value, VEHICLE_FIELDS)
        uid = self.world.facility(value["hub_id"]).facility_uid
        if value.get("facility_uid", uid) != uid:
            raise ValueError("Conflicting vehicle location identities.")
        location = (
            self.location(value["location_snapshot"])
            if value.get("location_snapshot")
            else self.world.facility(uid).location_snapshot()
        )
        return OwnedVehicle(
            id=value["id"],
            name=value["name"],
            mode=value["mode"],
            capacity_tons=value["capacity_tons"],
            facility_uid=uid,
            status=value["status"],
            model_id=value.get("model_id"),
            operating_cost_eur_per_km=value.get("operating_cost_eur_per_km"),
            location=location,
        )

    def offer(self, value: dict[str, Any]) -> ContractOffer:
        """Restore historical NHM facts without consulting current profiles."""
        reject_unknown_fields(value, OFFER_FIELDS)
        origin = self.location(value["origin"])
        destination = self.location(value["destination"])
        for prefix, endpoint in (
            ("origin", origin),
            ("destination", destination),
        ):
            for suffix in ("hub_id", "facility_uid"):
                if value[prefix + "_" + suffix] != endpoint.facility_uid:
                    raise ValueError("Conflicting offer endpoints.")
        origin_profile = read_legacy_profile(value["origin_cargo_evidence"])
        destination_profile = read_legacy_profile(
            value["destination_cargo_evidence"]
        )
        if value["cargo_evidence"] != value["origin_cargo_evidence"]:
            raise ValueError("Conflicting cargo evidence.")
        product = next(
            (
                p.product
                for p in (origin_profile, destination_profile)
                if p.product.code == value["cargo_code"]
            ),
            None,
        )
        if product is None or product.name != value["cargo"]:
            raise ValueError("Historical cargo does not match its evidence.")
        return ContractOffer(
            id=value["id"],
            market_model=value["market_model"],
            cargo_system=value["cargo_system"],
            origin=origin,
            destination=destination,
            shipper_name=value["shipper_name"],
            consignee_name=value["consignee_name"],
            cargo=product,
            origin_cargo_evidence=origin_profile,
            destination_cargo_evidence=destination_profile,
            cargo_basis=value["cargo_basis"],
            trade_match_type=value["trade_match_type"],
            tons=value["tons"],
            payload_band=value["payload_band"],
            rate_eur_per_km_ton=value["rate_eur_per_km_ton"],
            created_at=value["created_at"],
            expires_at=value["expires_at"],
            mode=value["mode"],
            relationship_simulated=value["relationship_simulated"],
        )

    def validate_obsolete_offer(self, value: dict[str, Any]) -> None:
        """Validate known retired offers before reporting their exclusion."""
        reject_unknown_fields(value, OFFER_FIELDS)
        for field in ("id", "cargo", "shipper_name", "consignee_name", "mode"):
            require_identity(value[field], "Historical offer field")
        require_finite(value["tons"], "Tonnage", 0.01)
        require_finite(value["created_at"], "Creation")
        require_finite(value["expires_at"], "Expiry")
        if value["expires_at"] <= value["created_at"]:
            raise ValueError("Invalid obsolete offer timeline.")
        origin = self.location(value["origin"])
        destination = self.location(value["destination"])
        if origin.facility_uid == destination.facility_uid:
            raise ValueError("Identical obsolete offer endpoints.")
        for prefix, location in (
            ("origin", origin),
            ("destination", destination),
        ):
            if any(
                value[prefix + "_" + suffix] != location.facility_uid
                for suffix in ("hub_id", "facility_uid")
            ):
                raise ValueError("Conflicting obsolete offer endpoints.")

    def historical_contract(
        self, value: dict[str, Any]
    ) -> HistoricalContractSnapshot:
        """Preserve NHM or documented goods without inventing facts."""
        if value.get("market_model") is not None:
            return HistoricalContractSnapshot.from_offer(self.offer(value))
        self.validate_obsolete_offer(value)
        cargo = read_documented_cargo(value["cargo_evidence"])
        if cargo.code != value["cargo_code"] or cargo.name != value["cargo"]:
            raise ValueError("Historical description differs from evidence.")
        return HistoricalContractSnapshot(
            id=value["id"],
            origin=self.location(value["origin"]),
            destination=self.location(value["destination"]),
            shipper_name=value["shipper_name"],
            consignee_name=value["consignee_name"],
            cargo=cargo,
            tons=value["tons"],
            created_at=value["created_at"],
            expires_at=value["expires_at"],
            mode=value["mode"],
            relationship_simulated=value["relationship_simulated"],
            cargo_basis=value["cargo_basis"],
            payload_band=value["payload_band"],
            rate_eur_per_km_ton=value["rate_eur_per_km_ton"],
        )

    def transport(self, value: dict[str, Any]) -> ActiveTransport:
        """Copy the saved route, timeline and economics; never reroute."""
        reject_unknown_fields(value, TRANSPORT_FIELDS)
        geometry = value["route_geojson"]
        if geometry["type"] == "Feature":
            geometry = geometry["geometry"]
        if geometry["type"] != "LineString":
            raise ValueError("Unsupported historical route geometry.")
        if (
            value["profit_eur"]
            != value["payout_eur"] - value["operating_cost_eur"]
        ):
            raise ValueError("Conflicting historical economics.")
        if (
            value["origin"] != value["origin_snapshot"]
            or value["destination"] != value["destination_snapshot"]
        ):
            raise ValueError("Conflicting transport endpoint snapshots.")
        return ActiveTransport(
            id=value["id"],
            vehicle_id=value["vehicle_id"],
            contract=self.historical_contract(value["contract"]),
            origin=self.location(value["origin_snapshot"]),
            destination=self.location(value["destination_snapshot"]),
            route=RouteSnapshot(
                tuple(tuple(point) for point in geometry["coordinates"]),
                value["distance_km"],
                value["routing_duration_seconds"],
                value["provider"],
            ),
            departed_at=value["departed_at"],
            arrives_at=value["arrives_at"],
            payout_eur=value["payout_eur"],
            operating_cost_eur=value["operating_cost_eur"],
            status=value.get("status", "active"),
            settled_at=value.get("settled_at"),
        )


def read_legacy_profile(value: dict[str, Any]) -> FacilityNhmProfile:
    """Separate the saved product hierarchy from saved handling evidence."""
    return FacilityNhmProfile(
        product=NhmProduct(
            value["nhm_row_id"],
            value["code"],
            value["name"],
            tuple(value["ancestor_row_ids"]),
        ),
        role=value["role"],
        evidence_type=value["evidence_type"],
        confidence=value["confidence"],
        priority_score=value["priority_score"],
        source=SourceReference(**value["source"]) if value["source"] else None,
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
    value: dict[str, Any], allowed: frozenset[str]
) -> None:
    """Fail closed on unrecognized documents rather than losing new fields."""
    if not isinstance(value, dict) or value.keys() - allowed:
        raise ValueError("Unknown legacy snapshot fields.")


def read_documented_cargo(value: dict[str, Any]) -> DocumentedCargo:
    """Retain an older documented classification as its own historical fact."""
    return DocumentedCargo(
        **{
            **value,
            "source": SourceReference(**value["source"])
            if value["source"]
            else None,
        }
    )
