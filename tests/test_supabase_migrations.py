"""Static contracts for production-only Supabase migrations."""

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1]
    / "supabase"
    / "migrations"
    / "20261002114339_harden_private_schemas.sql"
)
PRIVATE_SCHEMAS = ("game", "world_catalogue", "vehicle_catalogue")
RUNTIME_FOREIGN_KEY_INDEXES = (
    "market_offer_templates_template_id_idx",
    "market_template_uses_template_id_idx",
    "sessions_user_id_idx",
)


def test_private_schema_hardening_migration_is_complete() -> None:
    migration = MIGRATION.read_text(encoding="utf-8").lower()

    for schema in PRIVATE_SCHEMAS:
        assert f"revoke all privileges on schema {schema}" in migration
        assert f"all tables in schema {schema}" in migration
        assert f"all functions in schema {schema}" in migration
        assert f"default privileges in schema {schema}" in migration
    assert "enable row level security" in migration
    assert "from public, anon, authenticated" in migration
    for index_name in RUNTIME_FOREIGN_KEY_INDEXES:
        assert f"index if not exists {index_name}" in migration
