"""Small SQLite catalogues for repository tests and failure mutations."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue
from tests.support.catalogues import BERLIN_UID

WORLD_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE countries(code TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE cities(
    city_uid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL REFERENCES countries(code),
    region TEXT
);
CREATE TABLE sources(
    source_id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    name TEXT NOT NULL,
    base_url TEXT,
    license_name TEXT,
    license_url TEXT,
    retrieved_at TEXT,
    notes TEXT
);
CREATE TABLE companies(
    company_id INTEGER PRIMARY KEY,
    legal_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    lei TEXT,
    country_code TEXT NOT NULL REFERENCES countries(code),
    website_url TEXT,
    entity_status TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company_uid TEXT NOT NULL
);
CREATE UNIQUE INDEX uq_company_uid ON companies(company_uid);
CREATE TRIGGER preserve_company_uid
BEFORE UPDATE OF company_uid ON companies
BEGIN
    SELECT RAISE(ABORT, 'immutable company uid');
END;
CREATE TABLE company_sources(
    company_id INTEGER NOT NULL REFERENCES companies(company_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL,
    source_role TEXT NOT NULL,
    verified_at TEXT,
    PRIMARY KEY(company_id, source_id, source_role)
);
CREATE TABLE facility_types(
    facility_type_id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL
);
CREATE TABLE facilities(
    facility_id INTEGER PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id),
    facility_type_id INTEGER NOT NULL REFERENCES facility_types(
        facility_type_id
    ),
    name TEXT NOT NULL,
    street TEXT,
    house_number TEXT,
    postcode TEXT,
    latitude REAL,
    longitude REAL,
    osm_type TEXT,
    osm_id INTEGER,
    website_url TEXT,
    verification_status TEXT NOT NULL,
    company_link_confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    geocoding_status TEXT NOT NULL,
    facility_uid TEXT NOT NULL,
    city_uid TEXT NOT NULL REFERENCES cities(city_uid)
);
CREATE UNIQUE INDEX uq_facility_uid ON facilities(facility_uid);
CREATE TRIGGER preserve_facility_uid
BEFORE UPDATE OF facility_uid ON facilities
BEGIN
    SELECT RAISE(ABORT, 'immutable facility uid');
END;
CREATE TRIGGER coordinate_pair_update
BEFORE UPDATE OF latitude, longitude ON facilities
WHEN (NEW.latitude IS NULL) != (NEW.longitude IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'incomplete coordinates');
END;
CREATE TABLE facility_sources(
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL,
    source_role TEXT NOT NULL,
    verified_at TEXT,
    PRIMARY KEY(facility_id, source_id, source_role)
);
CREATE TABLE facility_geocoding_evidence(
    geocoding_evidence_id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    precision_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL,
    osm_type TEXT,
    osm_id INTEGER,
    verified_at TEXT NOT NULL,
    notes TEXT
);
CREATE TABLE facility_aliases(
    alias TEXT PRIMARY KEY,
    facility_uid TEXT NOT NULL REFERENCES facilities(facility_uid)
);
CREATE TABLE cargo_types(
    cargo_type_id INTEGER PRIMARY KEY,
    nst_code TEXT NOT NULL,
    name TEXT NOT NULL
);
CREATE TABLE facility_handled_goods(
    handled_goods_id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    goods_description TEXT NOT NULL,
    cargo_type_id INTEGER REFERENCES cargo_types(cargo_type_id),
    evidence_type TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    notes TEXT
);
CREATE TABLE nhm_codes(
    nhm_row_id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    cnkey TEXT,
    level INTEGER NOT NULL,
    code_raw TEXT,
    code TEXT UNIQUE,
    code_length INTEGER,
    is_numeric INTEGER NOT NULL,
    name_de TEXT,
    label_de TEXT,
    name_en TEXT,
    label_en TEXT,
    name_fr TEXT,
    renvoi TEXT,
    renvoi_text_de TEXT,
    renvoi_text_en TEXT,
    renvoi_text_fr TEXT,
    consignment_note TEXT,
    parent_row_id INTEGER REFERENCES nhm_codes(nhm_row_id),
    effective_from TEXT NOT NULL,
    source_file TEXT NOT NULL
);
CREATE TABLE facility_nhm_profiles(
    profile_id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    nhm_row_id INTEGER NOT NULL REFERENCES nhm_codes(nhm_row_id),
    cargo_role TEXT NOT NULL,
    priority_score REAL NOT NULL,
    volume_band TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_id INTEGER REFERENCES sources(source_id),
    evidence_type TEXT NOT NULL,
    notes TEXT
);
CREATE TABLE nhm_market_profiles(
    nhm_row_id INTEGER PRIMARY KEY REFERENCES nhm_codes(nhm_row_id),
    transport_class TEXT NOT NULL,
    value_eur_per_t REAL NOT NULL,
    value_method TEXT NOT NULL,
    value_period TEXT NOT NULL,
    value_source_id INTEGER NOT NULL REFERENCES sources(source_id),
    value_confidence REAL NOT NULL,
    freight_rate_factor_game REAL NOT NULL,
    notes TEXT
);
CREATE TABLE nhm_distance_load_profiles(
    nhm_row_id INTEGER NOT NULL REFERENCES nhm_codes(nhm_row_id),
    distance_band TEXT NOT NULL,
    selection_weight REAL NOT NULL,
    load_factor_min REAL NOT NULL,
    load_factor_max REAL NOT NULL,
    PRIMARY KEY(nhm_row_id, distance_band)
);
CREATE TABLE nhm_vehicle_scale_profiles(
    nhm_row_id INTEGER NOT NULL REFERENCES nhm_codes(nhm_row_id),
    vehicle_scale TEXT NOT NULL,
    suitability_game REAL NOT NULL,
    notes TEXT NOT NULL,
    PRIMARY KEY(nhm_row_id, vehicle_scale)
);
CREATE TABLE external_identifiers(
    identifier_id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    identifier_type TEXT NOT NULL,
    identifier_value TEXT NOT NULL
);
"""

WORLD_DATA = f"""
INSERT INTO metadata VALUES('schema_version', '4.2.0');
INSERT INTO metadata VALUES('data_version', 'synthetic-sql-v1');
INSERT INTO metadata VALUES(
    'operational_profile_system',
    'NHM 2026 via facility_nhm_profiles -> nhm_codes'
);
INSERT INTO countries VALUES('DE', 'Germany');
INSERT INTO cities VALUES(
    '842dac5f-42b4-4fc7-bed1-5b487351e675',
    'Berlin', 'DE', 'Berlin'
);
INSERT INTO cities VALUES(
    '00000000-0000-0000-0000-000000000002',
    'Potsdam', 'DE', 'Brandenburg'
);
INSERT INTO sources VALUES(
    1, 'official', 'company', 'https://example.test/company',
    NULL, NULL, '2026-01-01', NULL
);
INSERT INTO sources VALUES(
    2, 'official', 'cargo', 'https://example.test/cargo',
    NULL, NULL, '2026-01-01', NULL
);
INSERT INTO companies VALUES(
    1, 'Synthetic Freight', 'Synthetic Freight', NULL, 'DE',
    'https://example.test/company', 'active', 'verified',
    '2026-01-01', '2026-01-01',
    '57f4d779-539c-4be8-a920-753bc205b5be'
);
INSERT INTO companies VALUES(
    2, 'Synthetic Logistics', 'Synthetic Logistics', NULL, 'DE',
    'https://example.test/logistics', 'active', 'verified',
    '2026-01-01', '2026-01-01',
    '00000000-0000-0000-0000-000000000003'
);
INSERT INTO company_sources VALUES(
    1, 1, 'https://example.test/company', 'official', '2026-01-01'
);
INSERT INTO company_sources VALUES(
    2, 1, 'https://example.test/logistics', 'official', '2026-01-01'
);
INSERT INTO facility_types VALUES(1, 'freight_terminal', 'Terminal');
INSERT INTO facilities VALUES(
    1, 1, 1, 'Berlin Test Terminal', 'Teststrasse', '1', '10000',
    52.5, 13.4, NULL, NULL, NULL, 'verified', 1,
    '2026-01-01', '2026-01-01', 'verified_coordinates',
    '{BERLIN_UID}', '842dac5f-42b4-4fc7-bed1-5b487351e675'
);
INSERT INTO facilities VALUES(
    2, 1, 1, 'Potsdam Test Terminal', NULL, NULL, NULL,
    52.4, 13.1, NULL, NULL, NULL, 'estimated', 1,
    '2026-01-01', '2026-01-01', 'estimated_for_simulation',
    '10000000-0000-4000-8000-000000000002',
    '00000000-0000-0000-0000-000000000002'
);
INSERT INTO facility_sources VALUES(
    1, 1, 'https://example.test/facility/1', 'official', '2026-01-01'
);
INSERT INTO facility_sources VALUES(
    2, 1, 'https://example.test/facility/2', 'official', '2026-01-01'
);
INSERT INTO facility_geocoding_evidence VALUES(
    1, 1, 52.5, 13.4, 'official_facility_coordinate', 'tests', 1,
    'https://example.test/facility/1', NULL, NULL, '2026-01-01', NULL
);
INSERT INTO facility_geocoding_evidence VALUES(
    2, 2, 52.4, 13.1, 'facility_centroid', 'tests', 1,
    'internal://simulation-test', NULL, NULL, '2026-01-01', NULL
);
INSERT INTO facility_aliases VALUES('berlin_westhafen', '{BERLIN_UID}');
INSERT INTO cargo_types VALUES(1, '01', 'General goods');
INSERT INTO facility_handled_goods VALUES(
    1, 1, 'Machine parts', 1, 'official', 2, NULL
);
INSERT INTO nhm_codes VALUES(
    100, 2, NULL, 1, '0100', '0100', 4, 1, 'Maschinenteile',
    'Maschinenteile', 'Machine parts', 'Machine parts', NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, '2026-01-01', 'synthetic'
);
INSERT INTO facility_nhm_profiles VALUES(
    1, 1, 100, 'both', 1, 'high', 1, 2, 'official', NULL
);
INSERT INTO nhm_market_profiles VALUES(
    100, 'general', 500, 'synthetic', '2026', 2, 1, 1, NULL
);
INSERT INTO nhm_distance_load_profiles VALUES(100, 'short', 1, .5, .8);
INSERT INTO nhm_distance_load_profiles VALUES(100, 'medium', 1, .5, .8);
INSERT INTO nhm_distance_load_profiles VALUES(100, 'long', 1, .5, .8);
INSERT INTO nhm_vehicle_scale_profiles VALUES(100, 'van', 1, 'synthetic');
INSERT INTO nhm_vehicle_scale_profiles VALUES(
    100, 'light_distribution', 1, 'synthetic'
);
INSERT INTO nhm_vehicle_scale_profiles VALUES(
    100, 'medium_distribution', 1, 'synthetic'
);
INSERT INTO nhm_vehicle_scale_profiles VALUES(100, 'heavy', 1, 'synthetic');
INSERT INTO external_identifiers VALUES(
    1, 'company', 1, 'tests', 'id', 'company-1'
);
INSERT INTO external_identifiers VALUES(
    2, 'facility', 1, 'tests', 'id', 'facility-1'
);
"""

VEHICLE_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE catalog_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE manufacturers(
    manufacturer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE vehicle_models(
    vehicle_id TEXT PRIMARY KEY,
    manufacturer_id TEXT NOT NULL REFERENCES manufacturers(manufacturer_id),
    model TEXT NOT NULL,
    variant TEXT NOT NULL,
    segment TEXT NOT NULL,
    powertrain TEXT NOT NULL,
    fuel_type TEXT NOT NULL,
    engine_code TEXT,
    displacement_l REAL,
    power_kw INTEGER NOT NULL,
    torque_nm INTEGER,
    battery_installed_kwh REAL,
    battery_usable_kwh REAL,
    charging_ccs_kw INTEGER,
    charging_mcs_kw INTEGER,
    axle_configuration TEXT,
    gearbox TEXT,
    gvw_kg INTEGER,
    gcw_kg INTEGER,
    range_km_claimed INTEGER,
    emissions_standard TEXT,
    consumption_value REAL,
    consumption_unit TEXT,
    fuel_tank_capacity_l REAL,
    fuel_tank_capacity_kg REAL,
    top_speed_kmh INTEGER
);
CREATE TABLE vehicle_balance(
    vehicle_id TEXT PRIMARY KEY REFERENCES vehicle_models(vehicle_id),
    purchase_price_eur_game INTEGER NOT NULL,
    operating_cost_eur_per_km_game REAL NOT NULL,
    maintenance_eur_per_1000_km_game INTEGER NOT NULL,
    payload_t_game REAL NOT NULL,
    reliability_score_game INTEGER NOT NULL,
    unlock_reputation_game INTEGER NOT NULL,
    route_range_km_game INTEGER,
    energy_stop_minutes_game INTEGER
);
CREATE TABLE vehicle_transport_capabilities(
    vehicle_id TEXT NOT NULL REFERENCES vehicle_models(vehicle_id),
    transport_class TEXT NOT NULL,
    suitability_game REAL NOT NULL,
    notes TEXT,
    PRIMARY KEY(vehicle_id, transport_class)
);
CREATE TABLE sources(
    source_id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    publisher TEXT
);
CREATE TABLE licenses(
    license_id TEXT PRIMARY KEY,
    license_name TEXT NOT NULL,
    license_url TEXT NOT NULL,
    requires_attribution INTEGER NOT NULL,
    share_alike INTEGER NOT NULL
);
CREATE TABLE vehicle_images(
    image_id INTEGER PRIMARY KEY,
    vehicle_id TEXT NOT NULL REFERENCES vehicle_models(vehicle_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    license_id TEXT NOT NULL REFERENCES licenses(license_id),
    commons_file_title TEXT,
    direct_image_url TEXT NOT NULL,
    author TEXT NOT NULL,
    attribution_text TEXT NOT NULL,
    image_scope TEXT NOT NULL,
    local_filename TEXT,
    verification_status TEXT NOT NULL,
    checked_at TEXT,
    is_primary INTEGER NOT NULL
);
CREATE TABLE vehicle_sources(
    vehicle_id TEXT NOT NULL REFERENCES vehicle_models(vehicle_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_role TEXT NOT NULL,
    source_note TEXT,
    PRIMARY KEY(vehicle_id, source_id, source_role)
);
"""

VEHICLE_DATA = """
INSERT INTO catalog_metadata VALUES('schema_version', '2.2.0');
INSERT INTO manufacturers VALUES('daf', 'DAF');
INSERT INTO vehicle_models VALUES(
    'iveco_sway_500', 'daf', 'S-Way', '500',
    'heavy_long_haul_tractor', 'combustion', 'diesel', NULL, NULL,
    368, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, 24.5, 'l/100km', 1010, NULL, 90
);
INSERT INTO vehicle_balance VALUES(
    'iveco_sway_500', 149000, .51, 78, 24.2, 90, 0, NULL, NULL
);
INSERT INTO vehicle_transport_capabilities VALUES(
    'iveco_sway_500', 'general', 1, 'synthetic'
);
INSERT INTO vehicle_models VALUES(
    'daf_xg_plus_480', 'daf', 'XG+', '480',
    'heavy_long_haul_tractor', 'combustion', 'diesel', NULL, NULL,
    355, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, 22.3, 'l/100km', 845, NULL, 90
);
INSERT INTO vehicle_balance VALUES(
    'daf_xg_plus_480', 162000, .49, 80, 24.3, 90, 25, NULL, NULL
);
INSERT INTO vehicle_transport_capabilities VALUES(
    'daf_xg_plus_480', 'general', 1, 'synthetic'
);
INSERT INTO vehicle_models VALUES(
    'man_tgx_520', 'daf', 'TGX', '520',
    'heavy_long_haul_tractor', 'combustion', 'diesel', NULL, NULL,
    382, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, 24.5, 'l/100km', 910, NULL, 90
);
INSERT INTO vehicle_balance VALUES(
    'man_tgx_520', 158000, .53, 85, 24.2, 90, 0, NULL, NULL
);
INSERT INTO vehicle_transport_capabilities VALUES(
    'man_tgx_520', 'general', 1, 'synthetic'
);
INSERT INTO vehicle_models VALUES(
    'mercedes_eactros_600', 'daf', 'eActros', '600',
    'heavy_long_haul_tractor', 'battery_electric', 'electric', NULL,
    NULL, 400, NULL, 621, 600, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, 103, 'kWh/100km', NULL, NULL, 90
);
INSERT INTO vehicle_balance VALUES(
    'mercedes_eactros_600', 238000, .31, 62, 22, 90, 0, NULL, 35
);
INSERT INTO vehicle_transport_capabilities VALUES(
    'mercedes_eactros_600', 'general', 1, 'synthetic'
);
INSERT INTO sources VALUES(
    1, 'synthetic', 'https://commons.wikimedia.org/wiki/File:Test.jpg',
    'test', 'tests'
);
INSERT INTO licenses VALUES(
    'cc0', 'CC0 1.0', 'https://creativecommons.org/publicdomain/zero/1.0/',
    0, 0
);
INSERT INTO vehicle_images VALUES(
    1, 'iveco_sway_500', 1, 'cc0', 'File:Test.jpg',
    'https://upload.wikimedia.org/test.jpg', 'Test Author',
    'Test Author, CC0', 'model_family', NULL, 'verified',
    '2026-01-01', 1
);
INSERT INTO vehicle_sources VALUES(
    'iveco_sway_500', 1, 'technical_spec', 'synthetic'
);
"""


def create_small_world_catalogue(path: Path) -> SqliteWorldCatalogue:
    """Create a complete two-facility world repository fixture."""
    _create_database(path, WORLD_SCHEMA, WORLD_DATA)
    return SqliteWorldCatalogue(path)


def create_small_vehicle_catalogue(path: Path) -> SqliteVehicleCatalogue:
    """Create a complete two-model vehicle repository fixture."""
    _create_database(path, VEHICLE_SCHEMA, VEHICLE_DATA)
    return SqliteVehicleCatalogue(path)


def _create_database(path: Path, schema: str, data: str) -> None:
    """Initialize one isolated SQLite fixture from readable SQL."""
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(schema)
        connection.executescript(data)
