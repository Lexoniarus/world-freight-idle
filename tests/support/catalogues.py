"""Compact catalogue doubles and explicit reference-catalogue paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.energy import EnergyProfile
from app.domain.evidence import SourceReference
from app.domain.geography import Address, City, Coordinates, Country
from app.domain.market_profiles import (
    VEHICLE_SCALES,
    DistanceLoadProfile,
    NhmMarketProfile,
    TransportCapability,
    VehicleScaleProfile,
)
from app.domain.vehicles import VehicleModel
from app.domain.world import Facility, WorldSnapshot

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_WORLD_PATH = (
    REPOSITORY_ROOT / "data" / "world_freight_company_facility_mvp.sqlite3"
)
REFERENCE_VEHICLE_PATH = (
    REPOSITORY_ROOT / "data" / "world_freight_vehicle_catalog.sqlite3"
)

BERLIN_UID = "3edb5c81-a923-45d6-87e9-274e69a8b8db"
TEST_CATALOGUE_VERSION = "synthetic-test-v1"
_SOURCE = SourceReference(
    "internal://simulation-test-catalogue",
    "synthetic test data",
    None,
    provider="tests",
)


@dataclass(frozen=True, slots=True)
class InMemoryWorldCatalogue:
    """Return one immutable synthetic world snapshot without file access."""

    snapshot: WorldSnapshot

    def read(self) -> WorldSnapshot:
        """Return the configured immutable snapshot."""
        return self.snapshot


@dataclass(frozen=True, slots=True)
class InMemoryVehicleCatalogue:
    """Return immutable vehicle models without a database dependency."""

    models: tuple[VehicleModel, ...]

    def list_models(self) -> tuple[VehicleModel, ...]:
        """Return all configured vehicle models."""
        return self.models


def build_synthetic_world_catalogue() -> InMemoryWorldCatalogue:
    """Build a small world spanning all market distance bands."""
    germany = Country("DE", "Germany")
    france = Country("FR", "France")
    cities = (
        _city(1, "Berlin", germany),
        _city(2, "Potsdam", germany),
        _city(3, "Hamburg", germany),
        _city(4, "Paris", france),
    )
    products = (
        NhmProduct(100, "0100", "Machine parts", (100,)),
        NhmProduct(200, "0200", "Packaged food", (200,)),
        NhmProduct(300, "0300", "Construction goods", (300,)),
    )
    facilities = (
        _facility(
            BERLIN_UID,
            "Berlin Westhafen",
            cities[0],
            Coordinates(52.536, 13.343),
            products,
            "output",
            ("berlin_westhafen",),
        ),
        _facility(
            "10000000-0000-4000-8000-000000000002",
            "Berlin South Depot",
            cities[0],
            Coordinates(52.450, 13.430),
            products,
            "output",
        ),
        _facility(
            "10000000-0000-4000-8000-000000000003",
            "Potsdam Freight Yard",
            cities[1],
            Coordinates(52.390, 13.060),
            products,
            "input",
        ),
        _facility(
            "10000000-0000-4000-8000-000000000004",
            "Hamburg Port",
            cities[2],
            Coordinates(53.540, 9.990),
            products,
            "input",
        ),
        _facility(
            "10000000-0000-4000-8000-000000000005",
            "Paris Logistics North",
            cities[3],
            Coordinates(48.930, 2.350),
            products,
            "input",
        ),
        _facility(
            "10000000-0000-4000-8000-000000000006",
            "Paris Logistics South",
            cities[3],
            Coordinates(48.790, 2.360),
            products,
            "input",
        ),
    )
    profiles = tuple(_market_profile(product) for product in products)
    snapshot = WorldSnapshot(
        TEST_CATALOGUE_VERSION,
        (),
        facilities,
        (germany, france),
        cities,
        profiles,
    )
    return InMemoryWorldCatalogue(snapshot)


def build_synthetic_vehicle_catalogue() -> InMemoryVehicleCatalogue:
    """Build six representative truck models for gameplay tests."""
    specifications = (
        ("iveco_sway_500", "IVECO S-Way 500", "IVECO", "diesel"),
        ("renault_t_high_520", "Renault T High 520", "Renault", "diesel"),
        ("man_tgx_520", "MAN TGX 520", "MAN", "diesel"),
        ("daf_xg_plus_480", "DAF XG+ 480", "DAF", "diesel"),
        ("scania_r460_gas", "Scania R460 Gas", "Scania", "gas"),
        (
            "mercedes_eactros_600",
            "Mercedes eActros 600",
            "Mercedes-Benz",
            "electric",
        ),
    )
    models = tuple(
        _vehicle_model(index, *specification)
        for index, specification in enumerate(specifications)
    )
    return InMemoryVehicleCatalogue(models)


def _city(identifier: int, name: str, country: Country) -> City:
    return City(str(UUID(int=identifier)), name, country)


def _facility(
    identifier: str,
    label: str,
    city: City,
    coordinates: Coordinates,
    products: tuple[NhmProduct, ...],
    role: str,
    aliases: tuple[str, ...] = (),
) -> Facility:
    profiles = tuple(
        FacilityNhmProfile(product, role, "synthetic", 1, 1, _SOURCE)
        for product in products
    )
    return Facility(
        identifier,
        None,
        label,
        "freight_terminal",
        Address(city),
        coordinates,
        "estimated_for_simulation",
        (_SOURCE,),
        (_SOURCE,),
        profiles,
        TEST_CATALOGUE_VERSION,
        aliases,
    )


def _market_profile(product: NhmProduct) -> NhmMarketProfile:
    return NhmMarketProfile(
        product.nhm_row_id,
        "general",
        500,
        1,
        tuple(
            DistanceLoadProfile(band, 1, 0.5, 0.8)
            for band in ("short", "medium", "long")
        ),
        tuple(VehicleScaleProfile(scale, 1) for scale in VEHICLE_SCALES),
    )


def _vehicle_model(
    index: int,
    model_id: str,
    name: str,
    manufacturer: str,
    powertrain: str,
) -> VehicleModel:
    energy = {
        "diesel": EnergyProfile("diesel", "l", 900, 25, 10, 0.1),
        "gas": EnergyProfile("gas", "kg", 400, 22, 25, 0.1),
        "electric": EnergyProfile("electric", "kWh", 600, 103, 35, 0.1),
    }[powertrain]
    capabilities = tuple(
        TransportCapability(transport_class, suitability)
        for transport_class, suitability in (
            ("general", 1),
            ("parcel", 0.6),
            ("dry_bulk", 0.85),
            ("liquid_bulk", 0.85),
            ("temperature_controlled", 0.85),
            ("special", 0.75),
        )
    )
    return VehicleModel(
        model_id,
        name,
        manufacturer,
        powertrain,
        24 - index * 0.2,
        149_000 + index * 12_000,
        0.5,
        80,
        index * 5,
        energy,
        90,
        "heavy_long_haul_tractor",
        capabilities,
    )
