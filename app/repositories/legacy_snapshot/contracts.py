"""Historical contract and offer decoding."""

from dataclasses import dataclass
from typing import Any

from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.validation import require_finite, require_identity
from app.repositories.legacy_import_values import (
    OFFER_FIELDS,
    read_documented_cargo,
    read_legacy_profile,
    reject_unknown_fields,
)
from app.repositories.legacy_snapshot.locations import LegacyLocationReader


@dataclass(frozen=True, slots=True)
class LegacyContractReader:
    """Restore historical offer facts without current-market inference."""

    locations: LegacyLocationReader

    def read_offer(
        self, value: dict[str, Any], path: str = "offer"
    ) -> ContractOffer:
        """Restore historical NHM facts without current profiles."""
        reject_unknown_fields(value, OFFER_FIELDS, path)
        origin = self.locations.read(value["origin"], path + ".origin")
        destination = self.locations.read(
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
                profile.product
                for profile in (origin_profile, destination_profile)
                if profile.product.code == value["cargo_code"]
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
        """Validate retired offers before reporting their exclusion."""
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
        origin = self.locations.read(value["origin"], path + ".origin")
        destination = self.locations.read(
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

    def read_historical_contract(
        self, value: dict[str, Any], path: str = "contract"
    ) -> HistoricalContractSnapshot:
        """Preserve NHM or documented goods without inventing facts."""
        reject_unknown_fields(value, OFFER_FIELDS, path)
        if value.get("market_model") is not None:
            return HistoricalContractSnapshot.from_offer(
                self.read_offer(value, path)
            )
        self.validate_obsolete_offer(value, path)
        cargo = read_documented_cargo(
            value["cargo_evidence"], path + ".cargo_evidence"
        )
        return HistoricalContractSnapshot(
            id=value["id"],
            origin=self.locations.read(value["origin"], path + ".origin"),
            destination=self.locations.read(
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
