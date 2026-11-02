"""Historical facility-location decoding and identity reconciliation."""

from dataclasses import dataclass
from typing import Any

from app.domain.cargo import DocumentedCargo, FacilityNhmProfile
from app.domain.geography import City, Coordinates
from app.domain.world import (
    DocumentedGood,
    Facility,
    FacilityLocationSnapshot,
    ReferenceCompanyIdentity,
)
from app.domain.world_scopes import WorldScope
from app.repositories.legacy_import_values import (
    COMPANY_FIELDS,
    LOCATION_FIELDS,
    read_documented_cargo,
    read_legacy_good,
    read_legacy_profile,
    read_legacy_sources,
    reject_unknown_fields,
    require_legacy_array,
)


@dataclass(frozen=True, slots=True)
class LegacyLocationReader:
    """Restore saved locations around canonical world identities."""

    world: WorldScope

    def read(
        self, value: dict[str, Any], path: str = "location"
    ) -> FacilityLocationSnapshot:
        """Add the reviewed city UID while retaining historical facts."""
        reject_unknown_fields(value, LOCATION_FIELDS, path)
        reference = self._validate_identity(value, path)
        company = self._read_company_identity(value, path)
        return FacilityLocationSnapshot(
            facility_uid=reference.facility_uid,
            company=company,
            label=value["label"],
            facility_type=value["facility_type"],
            city=self._read_city_identity(value, reference),
            address=value["address"],
            coordinates=self._read_coordinates(value),
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
            handled_goods=self._read_handled_goods(value, path),
            handling_evidence=self._read_handling_evidence(value, path),
        )

    def _validate_identity(self, value: dict[str, Any], path: str) -> Facility:
        """Resolve the facility and reject conflicting historical keys."""
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
        return reference

    def _read_city_identity(
        self, value: dict[str, Any], reference: Facility
    ) -> City:
        """Restore the saved label around the canonical city identity."""
        country = self.world.country(value["country"]).country
        return City(
            reference.address.city.city_uid,
            value["city"],
            country,
            reference.address.city.region,
        )

    def _read_company_identity(
        self, value: dict[str, Any], path: str
    ) -> ReferenceCompanyIdentity | None:
        """Decode either a complete or compact historical company."""
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
        return company

    @staticmethod
    def _read_coordinates(value: dict[str, Any]) -> Coordinates | None:
        """Decode an optional complete coordinate pair."""
        if (value["lat"] is None) != (value["lon"] is None):
            raise ValueError("Incomplete historical coordinates.")
        if value["lat"] is None:
            return None
        return Coordinates(value["lat"], value["lon"])

    @staticmethod
    def _read_handled_goods(
        value: dict[str, Any], path: str
    ) -> tuple[DocumentedGood, ...]:
        """Decode retained free-text handling facts."""
        return tuple(
            read_legacy_good(item, f"{path}.handled_goods[{index}]")
            for index, item in enumerate(
                require_legacy_array(
                    value.get("handled_goods", []), path + ".handled_goods"
                )
            )
        )

    @staticmethod
    def _read_handling_evidence(
        value: dict[str, Any], path: str
    ) -> tuple[FacilityNhmProfile | DocumentedCargo, ...]:
        """Decode NHM profiles and documented cargo without conversion."""
        return tuple(
            read_legacy_profile(item, f"{path}.cargo[{index}]")
            if isinstance(item, dict) and "nhm_row_id" in item
            else read_documented_cargo(item, f"{path}.cargo[{index}]")
            for index, item in enumerate(
                require_legacy_array(value.get("cargo", []), path + ".cargo")
            )
        )
