"""Strict, offline-only decoding of the former KV snapshot documents."""

from typing import Any

from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.game import OwnedVehicle
from app.domain.geography import City, Coordinates
from app.domain.journeys import unmetered_journey
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.domain.validation import require_finite, require_identity
from app.domain.vehicles import VehicleModel
from app.domain.world import FacilityLocationSnapshot, ReferenceCompanyIdentity
from app.domain.world_scopes import WorldScope
from app.repositories.legacy_import_values import (
    COMPANY_FIELDS,
    LOCATION_FIELDS,
    OFFER_FIELDS,
    TRANSPORT_FIELDS,
    VEHICLE_FIELDS,
    read_documented_cargo,
    read_legacy_good,
    read_legacy_profile,
    read_legacy_route,
    read_legacy_sources,
    reject_unknown_fields,
    require_legacy_array,
)


class LegacySnapshotReader:
    """Resolve new city identities while preserving saved historical facts."""

    def __init__(
        self, world: WorldScope, models: tuple[VehicleModel, ...]
    ) -> None:
        self.world = world
        self.models = {model.id: model for model in models}

    def location(
        self, value: dict[str, Any], path: str = "location"
    ) -> FacilityLocationSnapshot:
        """Add the reviewed city UID, retaining old labels and coordinates."""
        reject_unknown_fields(value, LOCATION_FIELDS, path)
        if (
            value["snapshot_version"] != 1
            or value["location_kind"] != "public_facility"
        ):
            raise ValueError("Unknown location snapshot version or kind.")
        uid = value["facility_uid"]
        reference = self.world.facility(uid)
        if value.get("id", uid) != uid:
            raise ValueError("Conflicting historical facility identities.")
        if value.get("city_uid", reference.address.city.city_uid) != (
            reference.address.city.city_uid
        ):
            raise ValueError(
                f"Conflicting historical identity at {path}.city_uid"
            )
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
            reject_unknown_fields(
                raw_company, COMPANY_FIELDS, path + ".company"
            )
            company = ReferenceCompanyIdentity(
                raw_company["company_uid"],
                raw_company["legal_name"],
                raw_company["display_name"],
                self.world.country(raw_company["country"]).country,
                raw_company.get("website"),
                read_legacy_sources(
                    raw_company.get("sources", []), path + ".company.sources"
                ),
            )
        elif value.get("company_uid"):
            company = ReferenceCompanyIdentity(
                value["company_uid"], None, None, None
            )
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
            coordinate_evidence=read_legacy_sources(
                value["coordinate_evidence"], path + ".coordinate_evidence"
            ),
            catalogue_version=value["catalogue_version"],
            aliases=tuple(
                require_legacy_array(value["aliases"], path + ".aliases")
            ),
            resolution_status=value["resolution_status"],
            location_verified=value.get(
                "location_verified",
                value["geocoding_status"] == "verified_coordinates",
            ),
            snapshot_version=value["snapshot_version"],
            location_kind=value["location_kind"],
            sources=read_legacy_sources(
                value.get("sources", []), path + ".sources"
            ),
            handled_goods=tuple(
                read_legacy_good(item, f"{path}.handled_goods[{index}]")
                for index, item in enumerate(
                    require_legacy_array(
                        value.get("handled_goods", []), path + ".handled_goods"
                    )
                )
            ),
            handling_evidence=tuple(
                read_legacy_profile(item, f"{path}.cargo[{index}]")
                if isinstance(item, dict) and "nhm_row_id" in item
                else read_documented_cargo(item, f"{path}.cargo[{index}]")
                for index, item in enumerate(
                    require_legacy_array(
                        value.get("cargo", []), path + ".cargo"
                    )
                )
            ),
        )

    def vehicle(
        self, value: dict[str, Any], path: str = "vehicle"
    ) -> OwnedVehicle:
        """Retain purchased values and resolve the former public hub alias."""
        reject_unknown_fields(value, VEHICLE_FIELDS, path)
        uid = self.world.facility(value["hub_id"]).facility_uid
        if value.get("facility_uid", uid) != uid:
            raise ValueError("Conflicting vehicle location identities.")
        location = (
            self.location(
                value["location_snapshot"], path + ".location_snapshot"
            )
            if value.get("location_snapshot") is not None
            else self.location(value["hub"], path + ".hub")
            if value.get("hub") is not None
            else self.world.facility(uid).location_snapshot()
        )
        if value.get("hub") is not None:
            hub = self.location(value["hub"], path + ".hub")
            if hub != location:
                raise ValueError(
                    f"Conflicting historical location at {path}.hub"
                )
        model = self.models[value["model_id"]]
        return OwnedVehicle(
            energy=model.energy,
            energy_level=model.energy.capacity,
            top_speed_kmh=model.top_speed_kmh,
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

    def offer(
        self, value: dict[str, Any], path: str = "offer"
    ) -> ContractOffer:
        """Restore historical NHM facts without consulting current profiles."""
        reject_unknown_fields(value, OFFER_FIELDS, path)
        origin = self.location(value["origin"], path + ".origin")
        destination = self.location(
            value["destination"], path + ".destination"
        )
        for prefix, endpoint in (
            ("origin", origin),
            ("destination", destination),
        ):
            for suffix in ("hub_id", "facility_uid"):
                if value[prefix + "_" + suffix] != endpoint.facility_uid:
                    raise ValueError("Conflicting offer endpoints.")
        origin_profile = read_legacy_profile(
            value["origin_cargo_evidence"], path + ".origin_cargo_evidence"
        )
        destination_profile = read_legacy_profile(
            value["destination_cargo_evidence"],
            path + ".destination_cargo_evidence",
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

    def validate_obsolete_offer(
        self, value: dict[str, Any], path: str = "offer"
    ) -> None:
        """Validate known retired offers before reporting their exclusion."""
        reject_unknown_fields(value, OFFER_FIELDS, path)
        for field in ("id", "cargo", "shipper_name", "consignee_name", "mode"):
            require_identity(value[field], "Historical offer field")
        for field in (
            "cargo_evidence",
            "origin_cargo_evidence",
            "destination_cargo_evidence",
        ):
            if field != "cargo_evidence" and value.get(field) is None:
                continue
            raw = value[field]
            cargo = (
                read_legacy_profile(raw, path + "." + field).product
                if isinstance(raw, dict) and "nhm_row_id" in raw
                else read_documented_cargo(raw, path + "." + field)
            )
            if field == "cargo_evidence" and (
                cargo.code != value["cargo_code"]
                or cargo.name != value["cargo"]
            ):
                raise ValueError(
                    f"Conflicting historical cargo at {path}.{field}"
                )
        require_finite(value["tons"], "Tonnage", 0.01)
        require_finite(value["created_at"], "Creation")
        require_finite(value["expires_at"], "Expiry")
        if value["expires_at"] <= value["created_at"]:
            raise ValueError("Invalid obsolete offer timeline.")
        origin = self.location(value["origin"], path + ".origin")
        destination = self.location(
            value["destination"], path + ".destination"
        )
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
        self, value: dict[str, Any], path: str = "contract"
    ) -> HistoricalContractSnapshot:
        """Preserve NHM or documented goods without inventing facts."""
        reject_unknown_fields(value, OFFER_FIELDS, path)
        if value.get("market_model") is not None:
            return HistoricalContractSnapshot.from_offer(
                self.offer(value, path)
            )
        self.validate_obsolete_offer(value, path)
        cargo = read_documented_cargo(
            value["cargo_evidence"], path + ".cargo_evidence"
        )
        return HistoricalContractSnapshot(
            id=value["id"],
            origin=self.location(value["origin"], path + ".origin"),
            destination=self.location(
                value["destination"], path + ".destination"
            ),
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

    def transport(
        self, value: dict[str, Any], path: str = "transport"
    ) -> ActiveTransport:
        """Copy the saved route, timeline and economics; never reroute."""
        reject_unknown_fields(value, TRANSPORT_FIELDS, path)
        coordinates = read_legacy_route(
            value["route_geojson"], path + ".route_geojson"
        )
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
            contract=self.historical_contract(
                value["contract"], path + ".contract"
            ),
            origin=self.location(
                value["origin_snapshot"], path + ".origin_snapshot"
            ),
            destination=self.location(
                value["destination_snapshot"], path + ".destination_snapshot"
            ),
            route=RouteSnapshot(
                coordinates,
                value["distance_km"],
                value["routing_duration_seconds"],
                value["provider"],
            ),
            departed_at=value["departed_at"],
            arrives_at=value["arrives_at"],
            journey=unmetered_journey(
                value["distance_km"],
                value["arrives_at"] - value["departed_at"],
            ),
            payout_eur=value["payout_eur"],
            operating_cost_eur=value["operating_cost_eur"],
            status=value.get("status", "active"),
            settled_at=value.get("settled_at"),
        )
