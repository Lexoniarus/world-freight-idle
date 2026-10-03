"""Build deterministic ignored SQLite catalogues for isolated tests."""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Callable

WORLD_FILENAME = "world_freight_company_facility_mvp.sqlite3"
VEHICLE_FILENAME = "world_freight_vehicle_catalog.sqlite3"

WOLFSBURG_UID = "53e47547-aa34-4234-a41c-4fe81bb86290"
STENDAL_UID = "18e6c54b-658c-4a10-ab92-d518bca060f7"


class CatalogueFixtureBuilder:
    """Materialize reproducible test catalogues without production data."""

    def __init__(self, data_directory: Path) -> None:
        self.data_directory = data_directory

    def ensure(self) -> tuple[Path, Path]:
        """Create only missing ignored fixtures and return both paths."""
        self.data_directory.mkdir(parents=True, exist_ok=True)
        world_path = self.data_directory / WORLD_FILENAME
        vehicle_path = self.data_directory / VEHICLE_FILENAME
        self._ensure_database(world_path, self._populate_world)
        self._ensure_database(vehicle_path, self._populate_vehicles)
        return world_path, vehicle_path

    def _ensure_database(
        self,
        target: Path,
        populate: Callable[[sqlite3.Connection], None],
    ) -> None:
        """Publish a complete temporary database without replacing a fixture."""
        if target.exists():
            return
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        temporary.unlink(missing_ok=True)
        try:
            with closing(sqlite3.connect(temporary)) as connection:
                with connection:
                    connection.execute("PRAGMA foreign_keys=ON")
                    populate(connection)
                    if connection.execute(
                        "PRAGMA foreign_key_check"
                    ).fetchone():
                        raise ValueError(
                            "Generated fixture has broken references."
                        )
                    if (
                        connection.execute(
                            "PRAGMA integrity_check"
                        ).fetchone()[0]
                        != "ok"
                    ):
                        raise ValueError(
                            "Generated fixture failed integrity check."
                        )
            if not target.exists():
                temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def _populate_world(self, connection: sqlite3.Connection) -> None:
        """Create a compact relational world with production-shaped behavior."""
        connection.executescript(WORLD_SCHEMA)
        connection.executemany(
            "INSERT INTO metadata(key,value) VALUES (?,?)",
            (
                ("schema_version", "4.2.0"),
                ("data_version", "test-2026-10-02"),
                (
                    "operational_profile_system",
                    "NHM 2026 via facility_nhm_profiles -> nhm_codes",
                ),
            ),
        )
        connection.execute("INSERT INTO countries VALUES ('DE','Germany')")
        cities = _world_cities()
        connection.executemany(
            "INSERT INTO cities VALUES (?,?,?,?)",
            cities,
        )
        connection.executemany(
            "INSERT INTO companies VALUES (?,?,?,?,?,?)",
            (
                (
                    1,
                    "Fixture Logistics AG",
                    "Fixture Logistics",
                    "DE",
                    "https://example.test/company",
                    _stable_uuid(1),
                ),
                (
                    2,
                    "Second Fixture Logistics AG",
                    "Second Fixture Logistics",
                    "DE",
                    "https://example.test/company-two",
                    _stable_uuid(2),
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO sources VALUES (?,?,?,?,?)",
            (
                (
                    1,
                    "company",
                    "Fixture company source",
                    "https://example.test/company",
                    "2026-10-02",
                ),
                (
                    2,
                    "cargo",
                    "Fixture cargo source",
                    "https://example.test/cargo",
                    "2026-10-02",
                ),
                (
                    3,
                    "facility",
                    "Fixture facility source",
                    "https://example.test/facility",
                    "2026-10-02",
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO company_sources VALUES (?,1,?,?,?)",
            (
                (
                    1,
                    "https://example.test/company",
                    "official",
                    "2026-10-02",
                ),
                (
                    2,
                    "https://example.test/company-two",
                    "official",
                    "2026-10-02",
                ),
            ),
        )
        connection.execute(
            "INSERT INTO facility_types VALUES (1,'terminal','Terminal')"
        )
        connection.execute(
            "INSERT INTO cargo_types VALUES (1,'01','General cargo')"
        )
        connection.executemany(
            """INSERT INTO nhm_codes(
                   nhm_row_id,source_id,code,level,name_de,label_de,is_numeric,
                   parent_row_id,effective_from,source_file,cnkey
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                (
                    1,
                    2,
                    "0101",
                    1,
                    "General cargo",
                    "General cargo",
                    1,
                    None,
                    "2026-01-01",
                    "fixture",
                    None,
                ),
                (
                    2,
                    2,
                    "010101",
                    2,
                    "Derived cargo",
                    "Derived cargo",
                    1,
                    1,
                    "2026-01-01",
                    "fixture",
                    None,
                ),
            ),
        )
        for nhm_row_id in (1, 2):
            connection.execute(
                "INSERT INTO nhm_market_profiles VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    nhm_row_id,
                    "general" if nhm_row_id == 1 else "special",
                    500.0,
                    "fixture",
                    "2026",
                    2,
                    1.0,
                    1.0,
                    "deterministic test profile",
                ),
            )
            connection.executemany(
                "INSERT INTO nhm_distance_load_profiles VALUES (?,?,?,?,?)",
                (
                    (nhm_row_id, "short", 1.0, 0.4, 0.8),
                    (nhm_row_id, "medium", 1.0, 0.5, 0.9),
                    (nhm_row_id, "long", 1.0, 0.6, 1.0),
                ),
            )
            connection.executemany(
                "INSERT INTO nhm_vehicle_scale_profiles VALUES (?,?,?,?)",
                (
                    (nhm_row_id, "van", 0.4, "fixture"),
                    (nhm_row_id, "light_distribution", 0.7, "fixture"),
                    (nhm_row_id, "medium_distribution", 0.9, "fixture"),
                    (nhm_row_id, "heavy", 1.0, "fixture"),
                ),
            )
        self._insert_facilities(connection, cities)
        connection.executemany(
            "INSERT INTO external_identifiers VALUES (?,?,?,?,?)",
            (
                (1, "company", 1, "fixture", "company-1"),
                (2, "facility", 1, "fixture", "facility-1"),
            ),
        )
        connection.execute(
            "INSERT INTO facility_aliases VALUES (?,?)",
            ("berlin_westhafen", _stable_uuid(2000)),
        )
        connection.execute(
            "INSERT INTO facility_aliases VALUES (?,?)",
            ("hamburg_cta", _stable_uuid(3004)),
        )
        connection.execute(
            "INSERT INTO facility_handled_goods VALUES (1,1,?,?,?,?)",
            ("General cargo", 1, "official", 2),
        )

    def _insert_facilities(
        self,
        connection: sqlite3.Connection,
        cities: tuple[tuple[str, str, str, str], ...],
    ) -> None:
        """Insert exact special endpoints plus deterministic bulk locations."""
        facilities = [
            (
                1,
                _stable_uuid(2000),
                "Berlin Westhafen",
                cities[0][0],
                52.5374096,
                13.3439412,
                "verified_coordinates",
            ),
            (
                2,
                WOLFSBURG_UID,
                "Wolfsburg Test Terminal",
                cities[1][0],
                52.433806,
                10.779611,
                "verified_coordinates",
            ),
            (
                3,
                STENDAL_UID,
                "Stendal Test Terminal",
                cities[2][0],
                52.605959,
                11.85784,
                "verified_coordinates",
            ),
            (
                4,
                _stable_uuid(2001),
                "Estimated Test Terminal",
                cities[3][0],
                50.0,
                8.0,
                "estimated_for_simulation",
            ),
        ]
        for index in range(555):
            if index < 4:
                city_uid = cities[0][0]
            elif index == 4:
                city_uid = cities[4][0]
            else:
                city_uid = cities[5 + index % (len(cities) - 5)][0]
            facilities.append(
                (
                    index + 5,
                    _stable_uuid(3000 + index),
                    f"Synthetic Terminal {index + 1:03d}",
                    city_uid,
                    47.0 + (index % 80) / 10,
                    5.0 + (index % 90) / 10,
                    "verified_coordinates",
                )
            )
        connection.executemany(
            """INSERT INTO facilities(
                   facility_id,company_id,facility_type_id,name,street,
                   house_number,postcode,latitude,longitude,
                   geocoding_status,facility_uid,city_uid
               ) VALUES (?,1,1,?,'Fixture Road','1','00000',?,?,?,?,?)""",
            (
                (facility_id, name, latitude, longitude, status, uid, city_uid)
                for facility_id, uid, name, city_uid, latitude, longitude, status in facilities
            ),
        )
        profile_id = 0
        for facility_id, _, _, _, latitude, longitude, status in facilities:
            connection.execute(
                "INSERT INTO facility_sources VALUES (?,3,?,?,?)",
                (
                    facility_id,
                    f"https://example.test/facility/{facility_id}",
                    "official",
                    "2026-10-02",
                ),
            )
            evidence_url = (
                f"internal://simulation-{facility_id}"
                if status == "estimated_for_simulation"
                else f"https://example.test/coordinates/{facility_id}"
            )
            connection.execute(
                """INSERT INTO facility_geocoding_evidence(
                       geocoding_evidence_id,facility_id,latitude,longitude,
                       precision_type,provider,source_id,source_url,verified_at
                   ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    facility_id,
                    facility_id,
                    latitude,
                    longitude,
                    "official_facility_coordinate",
                    "fixture",
                    3,
                    evidence_url,
                    "2026-10-02",
                ),
            )
            if facility_id == 1:
                profiles = ((1, "both", "official", 2),)
            elif 5 <= facility_id <= 8:
                profiles = ((2, "output", "official", 2),)
            else:
                profiles = (
                    (1, "both", "official", 2),
                    (
                        2,
                        "both",
                        "derived" if facility_id == 4 else "official",
                        None if facility_id == 4 else 2,
                    ),
                )
            for nhm_row_id, role, evidence_type, source_id in profiles:
                profile_id += 1
                connection.execute(
                    """INSERT INTO facility_nhm_profiles(
                           profile_id,facility_id,nhm_row_id,cargo_role,
                           priority_score,volume_band,confidence,source_id,
                           evidence_type,notes
                       ) VALUES (?,?,?,?,1,'medium',1,?,?, 'fixture')""",
                    (
                        profile_id,
                        facility_id,
                        nhm_row_id,
                        role,
                        source_id,
                        evidence_type,
                    ),
                )

    def _populate_vehicles(self, connection: sqlite3.Connection) -> None:
        """Create fourteen explicit vehicle offers with valid provenance."""
        connection.executescript(VEHICLE_SCHEMA)
        connection.execute(
            "INSERT INTO catalog_metadata VALUES ('schema_version','2.2.0')"
        )
        manufacturers = sorted(
            {(row[1], row[2]) for row in VEHICLES},
            key=lambda item: item[0],
        )
        connection.executemany(
            "INSERT INTO manufacturers VALUES (?,?)",
            manufacturers,
        )
        connection.execute(
            "INSERT INTO sources(source_id,source_name,source_url,source_kind,publisher) "
            "VALUES (1,'Fixture images','https://commons.wikimedia.org/wiki/Main_Page',"
            "'image','Wikimedia Commons')"
        )
        connection.execute(
            "INSERT INTO licenses VALUES "
            "('cc0','CC0 1.0','https://creativecommons.org/publicdomain/zero/1.0/',0,0)"
        )
        for image_id, row in enumerate(VEHICLES, 1):
            self._insert_vehicle(connection, image_id, row)
        connection.execute(
            "INSERT INTO vehicle_transport_capabilities VALUES (?,?,?,?)",
            (
                "iveco_sway_500",
                "special",
                1.0,
                "deterministic fixture",
            ),
        )

    def _insert_vehicle(
        self,
        connection: sqlite3.Connection,
        image_id: int,
        row: tuple,
    ) -> None:
        """Insert one model, balance, capability, source and image."""
        (
            vehicle_id,
            manufacturer_id,
            _,
            model,
            variant,
            segment,
            powertrain,
            fuel_type,
            power_kw,
            battery_kwh,
            diesel_l,
            gas_kg,
            consumption,
            consumption_unit,
            top_speed,
            price,
            operating_cost,
            maintenance,
            payload,
            unlock,
            stop_minutes,
        ) = row
        connection.execute(
            """INSERT INTO vehicle_models(
                   vehicle_id,manufacturer_id,model,variant,segment,powertrain,
                   fuel_type,power_kw,battery_usable_kwh,fuel_tank_capacity_l,
                   fuel_tank_capacity_kg,consumption_value,consumption_unit,
                   top_speed_kmh
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                vehicle_id,
                manufacturer_id,
                model,
                variant,
                segment,
                powertrain,
                fuel_type,
                power_kw,
                battery_kwh,
                diesel_l,
                gas_kg,
                consumption,
                consumption_unit,
                top_speed,
            ),
        )
        connection.execute(
            "INSERT INTO vehicle_balance VALUES (?,?,?,?,?,?,?,?,?)",
            (
                vehicle_id,
                price,
                operating_cost,
                maintenance,
                payload,
                95,
                unlock,
                None,
                stop_minutes,
            ),
        )
        connection.execute(
            "INSERT INTO vehicle_transport_capabilities VALUES (?,?,?,?)",
            (vehicle_id, "general", 1.0, "deterministic fixture"),
        )
        connection.execute(
            "INSERT INTO vehicle_sources VALUES (?,1,'technical_spec','fixture')",
            (vehicle_id,),
        )
        connection.execute(
            """INSERT INTO vehicle_images(
                   image_id,vehicle_id,source_id,license_id,direct_image_url,
                   author,attribution_text,image_scope,verification_status,
                   is_primary
               ) VALUES (?,?,1,'cc0',?,?,?,?,?,1)""",
            (
                image_id,
                vehicle_id,
                f"https://upload.wikimedia.org/wikipedia/commons/{image_id}/fixture.jpg",
                "Fixture photographer",
                "Fixture image, CC0",
                "model_family",
                "verified",
            ),
        )


def _stable_uuid(value: int) -> str:
    """Return one canonical deterministic UUID for synthetic identities."""
    return str(uuid.UUID(int=value))


def _world_cities() -> tuple[tuple[str, str, str, str], ...]:
    """Return exactly 333 canonical city identities."""
    cities = [
        (_stable_uuid(1000), "Berlin", "DE", "Berlin"),
        (_stable_uuid(1001), "Wolfsburg", "DE", "Lower Saxony"),
        (_stable_uuid(1002), "Stendal", "DE", "Saxony-Anhalt"),
        (_stable_uuid(1003), "Frankfurt", "DE", "Hesse"),
        (_stable_uuid(1100), "Hamburg", "DE", "Hamburg"),
    ]
    cities.extend(
        (
            _stable_uuid(1101 + index),
            f"Fixture City {index + 1:03d}",
            "DE",
            "Fixture Region",
        )
        for index in range(328)
    )
    return tuple(cities)


WORLD_SCHEMA = """
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE countries(code TEXT PRIMARY KEY,name TEXT NOT NULL);
CREATE TABLE cities(
    city_uid TEXT PRIMARY KEY,name TEXT NOT NULL,country_code TEXT NOT NULL
    REFERENCES countries(code),region TEXT
);
CREATE TABLE companies(
    company_id INTEGER PRIMARY KEY,legal_name TEXT NOT NULL,
    display_name TEXT NOT NULL,country_code TEXT NOT NULL
    REFERENCES countries(code),website_url TEXT,company_uid TEXT NOT NULL
);
CREATE UNIQUE INDEX uq_company_uid ON companies(company_uid);
CREATE TRIGGER preserve_company_uid BEFORE UPDATE OF company_uid ON companies
WHEN NEW.company_uid != OLD.company_uid BEGIN
    SELECT RAISE(ABORT,'company uid is immutable');
END;
CREATE TABLE sources(
    source_id INTEGER PRIMARY KEY,source_type TEXT NOT NULL,name TEXT NOT NULL,
    base_url TEXT,retrieved_at TEXT
);
CREATE TABLE company_sources(
    company_id INTEGER NOT NULL REFERENCES companies(company_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL,source_role TEXT NOT NULL,verified_at TEXT,
    PRIMARY KEY(company_id,source_id,source_role)
);
CREATE TABLE facility_types(
    facility_type_id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,name TEXT NOT NULL
);
CREATE TABLE facilities(
    facility_id INTEGER PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id),
    facility_type_id INTEGER NOT NULL REFERENCES facility_types(facility_type_id),
    name TEXT NOT NULL,street TEXT,house_number TEXT,postcode TEXT,
    latitude REAL,longitude REAL,geocoding_status TEXT NOT NULL,
    facility_uid TEXT NOT NULL,city_uid TEXT NOT NULL REFERENCES cities(city_uid),
    CHECK((latitude IS NULL) = (longitude IS NULL))
);
CREATE UNIQUE INDEX uq_facility_uid ON facilities(facility_uid);
CREATE TRIGGER preserve_facility_uid BEFORE UPDATE OF facility_uid ON facilities
WHEN NEW.facility_uid != OLD.facility_uid BEGIN
    SELECT RAISE(ABORT,'facility uid is immutable');
END;
CREATE TRIGGER coordinate_pair_update BEFORE UPDATE OF latitude,longitude ON facilities
WHEN (NEW.latitude IS NULL) != (NEW.longitude IS NULL) BEGIN
    SELECT RAISE(ABORT,'coordinate pair required');
END;
CREATE TABLE facility_sources(
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL,source_role TEXT NOT NULL,verified_at TEXT,
    PRIMARY KEY(facility_id,source_id,source_role)
);
CREATE TABLE facility_geocoding_evidence(
    geocoding_evidence_id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    latitude REAL NOT NULL,longitude REAL NOT NULL,precision_type TEXT NOT NULL,
    provider TEXT NOT NULL,source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_url TEXT NOT NULL,verified_at TEXT NOT NULL
);
CREATE TABLE facility_aliases(
    alias TEXT PRIMARY KEY,
    facility_uid TEXT NOT NULL REFERENCES facilities(facility_uid)
);
CREATE TABLE cargo_types(
    cargo_type_id INTEGER PRIMARY KEY,nst_code TEXT NOT NULL UNIQUE,name TEXT NOT NULL
);
CREATE TABLE facility_handled_goods(
    handled_goods_id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    goods_description TEXT NOT NULL,
    cargo_type_id INTEGER REFERENCES cargo_types(cargo_type_id),
    evidence_type TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(source_id)
);
CREATE TABLE nhm_codes(
    nhm_row_id INTEGER PRIMARY KEY,source_id INTEGER NOT NULL REFERENCES sources(source_id),
    code TEXT UNIQUE,level INTEGER NOT NULL,name_de TEXT,label_de TEXT,
    name_en TEXT,label_en TEXT,
    is_numeric INTEGER NOT NULL,parent_row_id INTEGER REFERENCES nhm_codes(nhm_row_id),
    effective_from TEXT NOT NULL,source_file TEXT NOT NULL,cnkey TEXT
);
CREATE TABLE facility_nhm_profiles(
    profile_id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
    nhm_row_id INTEGER NOT NULL REFERENCES nhm_codes(nhm_row_id),
    cargo_role TEXT NOT NULL,priority_score REAL NOT NULL,volume_band TEXT NOT NULL,
    confidence REAL NOT NULL,source_id INTEGER REFERENCES sources(source_id),
    evidence_type TEXT NOT NULL,notes TEXT
);
CREATE TABLE nhm_market_profiles(
    nhm_row_id INTEGER PRIMARY KEY REFERENCES nhm_codes(nhm_row_id),
    transport_class TEXT NOT NULL,value_eur_per_t REAL NOT NULL,
    value_method TEXT NOT NULL,value_period TEXT NOT NULL,
    value_source_id INTEGER NOT NULL REFERENCES sources(source_id),
    value_confidence REAL NOT NULL,freight_rate_factor_game REAL NOT NULL,notes TEXT
);
CREATE TABLE nhm_distance_load_profiles(
    nhm_row_id INTEGER NOT NULL REFERENCES nhm_codes(nhm_row_id),
    distance_band TEXT NOT NULL,selection_weight REAL NOT NULL,
    load_factor_min REAL NOT NULL,load_factor_max REAL NOT NULL,
    PRIMARY KEY(nhm_row_id,distance_band)
);
CREATE TABLE nhm_vehicle_scale_profiles(
    nhm_row_id INTEGER NOT NULL REFERENCES nhm_codes(nhm_row_id),
    vehicle_scale TEXT NOT NULL,suitability_game REAL NOT NULL,notes TEXT,
    PRIMARY KEY(nhm_row_id,vehicle_scale)
);
CREATE TABLE external_identifiers(
    identifier_id INTEGER PRIMARY KEY,entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,provider TEXT NOT NULL,identifier_value TEXT NOT NULL
);
"""

VEHICLE_SCHEMA = """
CREATE TABLE catalog_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE manufacturers(
    manufacturer_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE
);
CREATE TABLE sources(
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,source_name TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,source_kind TEXT NOT NULL,publisher TEXT
);
CREATE TABLE licenses(
    license_id TEXT PRIMARY KEY,license_name TEXT NOT NULL,
    license_url TEXT NOT NULL UNIQUE,requires_attribution INTEGER NOT NULL,
    share_alike INTEGER NOT NULL
);
CREATE TABLE vehicle_models(
    vehicle_id TEXT PRIMARY KEY,
    manufacturer_id TEXT NOT NULL REFERENCES manufacturers(manufacturer_id),
    model TEXT NOT NULL,variant TEXT NOT NULL,segment TEXT NOT NULL,
    powertrain TEXT NOT NULL,fuel_type TEXT NOT NULL,power_kw INTEGER NOT NULL,
    battery_usable_kwh REAL,fuel_tank_capacity_l REAL,fuel_tank_capacity_kg REAL,
    consumption_value REAL,consumption_unit TEXT,top_speed_kmh INTEGER
);
CREATE TABLE vehicle_balance(
    vehicle_id TEXT PRIMARY KEY REFERENCES vehicle_models(vehicle_id),
    purchase_price_eur_game INTEGER NOT NULL,
    operating_cost_eur_per_km_game REAL NOT NULL,
    maintenance_eur_per_1000_km_game INTEGER NOT NULL,
    payload_t_game REAL NOT NULL,reliability_score_game INTEGER NOT NULL,
    unlock_reputation_game INTEGER NOT NULL,route_range_km_game INTEGER,
    energy_stop_minutes_game INTEGER
);
CREATE TABLE vehicle_transport_capabilities(
    vehicle_id TEXT NOT NULL REFERENCES vehicle_models(vehicle_id),
    transport_class TEXT NOT NULL,suitability_game REAL NOT NULL,notes TEXT,
    PRIMARY KEY(vehicle_id,transport_class)
);
CREATE TABLE vehicle_sources(
    vehicle_id TEXT NOT NULL REFERENCES vehicle_models(vehicle_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    source_role TEXT NOT NULL,source_note TEXT,
    PRIMARY KEY(vehicle_id,source_id,source_role)
);
CREATE TABLE vehicle_images(
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id TEXT NOT NULL REFERENCES vehicle_models(vehicle_id),
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    license_id TEXT NOT NULL REFERENCES licenses(license_id),
    direct_image_url TEXT NOT NULL,author TEXT NOT NULL,
    attribution_text TEXT NOT NULL,image_scope TEXT NOT NULL,
    verification_status TEXT NOT NULL,is_primary INTEGER NOT NULL DEFAULT 0
);
"""

VEHICLES = (
    (
        "vw_crafter_35_130kw",
        "volkswagen_nutzfahrzeuge",
        "Volkswagen",
        "Crafter",
        "35 2.0 TDI",
        "light_commercial_van",
        "combustion",
        "diesel",
        130,
        None,
        75.0,
        None,
        9.0,
        "l/100km",
        160,
        52000,
        0.22,
        46,
        1.15,
        0,
        None,
    ),
    (
        "mercedes_sprinter_317_cdi",
        "mercedes_benz",
        "Mercedes-Benz",
        "Sprinter",
        "317 CDI",
        "light_commercial_van",
        "combustion",
        "diesel",
        125,
        None,
        93.0,
        None,
        9.4,
        "l/100km",
        160,
        55000,
        0.23,
        48,
        1.1,
        0,
        None,
    ),
    (
        "iveco_daily_35s18",
        "iveco",
        "IVECO",
        "Daily",
        "35S18",
        "light_commercial_van",
        "combustion",
        "diesel",
        129,
        None,
        70.0,
        None,
        10.5,
        "l/100km",
        160,
        58000,
        0.24,
        50,
        1.2,
        0,
        None,
    ),
    (
        "mercedes_atego_818_l",
        "mercedes_benz",
        "Mercedes-Benz",
        "Atego",
        "818 L",
        "light_distribution_truck",
        "combustion",
        "diesel",
        130,
        None,
        120.0,
        None,
        16.0,
        "l/100km",
        90,
        82000,
        0.34,
        62,
        2.0,
        2,
        None,
    ),
    (
        "mercedes_atego_1224_l",
        "mercedes_benz",
        "Mercedes-Benz",
        "Atego",
        "1224 L",
        "medium_distribution_truck",
        "combustion",
        "diesel",
        175,
        None,
        180.0,
        None,
        18.5,
        "l/100km",
        90,
        108000,
        0.4,
        70,
        5.1,
        5,
        None,
    ),
    (
        "man_tgl_12_250",
        "man",
        "MAN",
        "TGL",
        "12.250",
        "medium_distribution_truck",
        "combustion",
        "diesel",
        184,
        None,
        220.0,
        None,
        18.0,
        "l/100km",
        90,
        112000,
        0.39,
        68,
        5.3,
        5,
        None,
    ),
    (
        "iveco_sway_500",
        "iveco",
        "IVECO",
        "S-Way",
        "500 XC13",
        "heavy_long_haul_tractor",
        "combustion",
        "diesel",
        368,
        None,
        1010.0,
        None,
        24.5,
        "l/100km",
        90,
        149000,
        0.51,
        78,
        24.2,
        0,
        None,
    ),
    (
        "renault_t_high_520",
        "renault_trucks",
        "Renault Trucks",
        "T High",
        "520 DE13",
        "heavy_long_haul_tractor",
        "combustion",
        "diesel",
        390,
        None,
        900.0,
        None,
        25.5,
        "l/100km",
        90,
        154000,
        0.52,
        81,
        24.1,
        0,
        None,
    ),
    (
        "man_tgx_520",
        "man",
        "MAN",
        "TGX",
        "520",
        "heavy_long_haul_tractor",
        "combustion",
        "diesel",
        382,
        None,
        910.0,
        None,
        24.5,
        "l/100km",
        90,
        158000,
        0.53,
        85,
        24.2,
        0,
        None,
    ),
    (
        "daf_xg_plus_480",
        "daf",
        "DAF",
        "XG+",
        "480 MX-13",
        "heavy_long_haul_tractor",
        "combustion",
        "diesel",
        355,
        None,
        845.0,
        None,
        22.3,
        "l/100km",
        90,
        162000,
        0.49,
        80,
        24.3,
        5,
        None,
    ),
    (
        "mercedes_actros_l_380",
        "mercedes_benz",
        "Mercedes-Benz",
        "Actros L",
        "380 kW",
        "heavy_long_haul_tractor",
        "combustion",
        "diesel",
        380,
        None,
        900.0,
        None,
        25.0,
        "l/100km",
        90,
        164000,
        0.54,
        90,
        24.0,
        0,
        None,
    ),
    (
        "volvo_fh_aero_500_isave",
        "volvo_trucks",
        "Volvo Trucks",
        "FH Aero",
        "500 I-Save",
        "heavy_long_haul_tractor",
        "combustion",
        "diesel",
        368,
        None,
        900.0,
        None,
        23.49,
        "l/100km",
        90,
        174000,
        0.5,
        82,
        24.0,
        10,
        None,
    ),
    (
        "scania_r460_gas",
        "scania",
        "Scania",
        "R 460",
        "Gas",
        "heavy_long_haul_tractor",
        "gas",
        "biomethane",
        338,
        None,
        None,
        400.0,
        22.2,
        "kg/100km",
        90,
        188000,
        0.46,
        94,
        23.6,
        15,
        25,
    ),
    (
        "mercedes_eactros_600",
        "mercedes_benz",
        "Mercedes-Benz",
        "eActros 600",
        "LFP",
        "heavy_long_haul_tractor",
        "battery_electric",
        "electric",
        600,
        600.0,
        None,
        None,
        103.0,
        "kWh/100km",
        90,
        238000,
        0.31,
        62,
        22.0,
        25,
        35,
    ),
)
