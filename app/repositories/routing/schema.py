"""Additive relational schema for shared routing evidence."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS routing_connection_proofs (
    pair_id TEXT PRIMARY KEY,
    forward_id TEXT NOT NULL, forward_revision TEXT NOT NULL,
    reverse_id TEXT NOT NULL, reverse_revision TEXT NOT NULL,
    validation_version TEXT NOT NULL, anchors TEXT NOT NULL,
    checked_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_provider_revisions (
    provider TEXT PRIMARY KEY, revision TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_relations (
    relation_id TEXT PRIMARY KEY, revision TEXT NOT NULL,
    origin_uid TEXT NOT NULL, destination_uid TEXT NOT NULL,
    fingerprint TEXT NOT NULL, status TEXT NOT NULL,
    cache_key TEXT, failure_category TEXT, retry_at REAL,
    checked_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_leases (
    subject TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id TEXT NOT NULL, method TEXT NOT NULL, outcome TEXT NOT NULL,
    observed_at REAL NOT NULL, trace_id TEXT NOT NULL,
    candidate_lat REAL, candidate_lon REAL,
    provider_code INTEGER, provider_message TEXT
);
CREATE TABLE IF NOT EXISTS offer_route_references (
    user_id TEXT NOT NULL, contract_id TEXT NOT NULL,
    relation_id TEXT NOT NULL, revision TEXT NOT NULL,
    PRIMARY KEY (user_id, contract_id),
    FOREIGN KEY (user_id, contract_id)
        REFERENCES contract_offers(user_id, contract_id) ON DELETE CASCADE
);
"""
