"""Relational game-state schema, independent of reference catalogues."""

VERSION = "1.1.0"
SCHEMA = """
CREATE TABLE game_schema (version TEXT NOT NULL);
INSERT INTO game_schema VALUES ('1.1.0');
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE player_states (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    cash INTEGER NOT NULL CHECK(typeof(cash) = 'integer' AND cash >= 0),
    completed INTEGER NOT NULL
        CHECK(typeof(completed) = 'integer' AND completed >= 0),
    reputation INTEGER NOT NULL
        CHECK(typeof(reputation) = 'integer' AND reputation >= 0)
);
CREATE TABLE owned_vehicles (
    user_id TEXT NOT NULL REFERENCES player_states(user_id),
    vehicle_id TEXT NOT NULL,
    name TEXT NOT NULL,
    mode TEXT NOT NULL,
    model_id TEXT,
    capacity_tons REAL NOT NULL CHECK(capacity_tons > 0),
    operating_cost_eur_per_km REAL,
    status TEXT NOT NULL CHECK(status IN ('idle', 'enroute')),
    facility_uid TEXT NOT NULL,
    location_snapshot TEXT,
    energy_snapshot TEXT NOT NULL,
    energy_level REAL NOT NULL CHECK(energy_level >= 0),
    top_speed_kmh REAL NOT NULL CHECK(top_speed_kmh > 0),
    PRIMARY KEY (user_id, vehicle_id)
);
CREATE INDEX vehicles_location ON owned_vehicles(user_id, facility_uid);
CREATE TABLE contract_offers (
    user_id TEXT NOT NULL REFERENCES player_states(user_id),
    contract_id TEXT NOT NULL,
    origin_facility_uid TEXT NOT NULL,
    destination_facility_uid TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL CHECK(expires_at > created_at),
    market_model TEXT NOT NULL,
    offer_snapshot TEXT NOT NULL,
    PRIMARY KEY (user_id, contract_id),
    CHECK(origin_facility_uid <> destination_facility_uid)
);
CREATE INDEX offers_scope
    ON contract_offers(user_id, origin_facility_uid, expires_at);
CREATE TABLE transports (
    user_id TEXT NOT NULL,
    transport_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    contract_id TEXT NOT NULL,
    origin_facility_uid TEXT NOT NULL,
    destination_facility_uid TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active', 'settled')),
    departed_at REAL NOT NULL,
    arrives_at REAL NOT NULL CHECK(arrives_at > departed_at),
    settled_at REAL,
    operating_cost_eur INTEGER NOT NULL CHECK(operating_cost_eur >= 0),
    payout_eur INTEGER NOT NULL CHECK(payout_eur >= 0),
    transport_snapshot TEXT NOT NULL,
    PRIMARY KEY(user_id, transport_id),
    FOREIGN KEY(user_id, vehicle_id)
        REFERENCES owned_vehicles(user_id, vehicle_id),
    CHECK((status = 'active' AND settled_at IS NULL)
        OR (status = 'settled' AND settled_at IS NOT NULL
            AND settled_at >= arrives_at))
);
CREATE UNIQUE INDEX one_active_transport_per_vehicle
    ON transports(user_id, vehicle_id) WHERE status = 'active';
CREATE INDEX arrivals ON transports(user_id, status, arrives_at);
CREATE TRIGGER retain_settlement BEFORE UPDATE ON transports
WHEN OLD.status = 'settled'
BEGIN SELECT RAISE(ABORT, 'Settled transport is immutable'); END;
"""

REQUIRED_TABLES = {
    "game_schema",
    "users",
    "player_states",
    "owned_vehicles",
    "contract_offers",
    "transports",
}
