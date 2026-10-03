"""Read-only PostgreSQL adapters for the reference catalogues."""

from __future__ import annotations

import logging
from typing import Any, cast

import psycopg
from psycopg.conninfo import make_conninfo

from app.domain.errors import CatalogueError, WorldCatalogueError
from app.domain.vehicles import VehicleModel
from app.domain.world import WorldSnapshot
from app.repositories.postgres_database import (
    PostgresConnectionAdapter,
    require_schema_name,
)
from app.repositories.vehicle_catalogue import (
    QUERY,
    SqliteVehicleCatalogue,
    read_transport_capabilities,
)
from app.repositories.world_catalogue import (
    SqliteWorldCatalogue,
    read_world_snapshot,
)

LOGGER = logging.getLogger(__name__)


def _catalogue_conninfo(database_url: str, schema: str) -> str:
    """Build an isolated connection with a fixed catalogue search path."""
    safe_schema = require_schema_name(schema)
    return make_conninfo(
        database_url,
        options=f"-csearch_path={safe_schema},public",
        application_name="world-freight-idle-catalogue",
        connect_timeout=10,
    )


class PostgresWorldCatalogue(SqliteWorldCatalogue):
    """Read one immutable world revision from PostgreSQL/Supabase."""

    def __init__(
        self, database_url: str, schema: str = "world_catalogue"
    ) -> None:
        self.database_url = database_url
        self.schema = require_schema_name(schema)

    def read(self) -> WorldSnapshot:
        """Read and validate one repeatable, read-only PostgreSQL snapshot."""
        try:
            conninfo = _catalogue_conninfo(self.database_url, self.schema)
            with psycopg.connect(
                conninfo,
                autocommit=True,
                prepare_threshold=None,
            ) as raw:
                raw.execute(
                    cast(Any, f"SET search_path TO {self.schema}, public")
                )
                raw.execute(
                    "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ "
                    "READ ONLY"
                )
                try:
                    return read_world_snapshot(
                        cast(Any, PostgresConnectionAdapter(raw))
                    )
                finally:
                    raw.execute("ROLLBACK")
        except (psycopg.Error, ValueError, TypeError, KeyError) as exc:
            LOGGER.error(
                "World catalogue unavailable",
                extra={
                    "event": "world.catalogue_error",
                    "data": {"backend": "postgres", "error": str(exc)},
                },
            )
            raise WorldCatalogueError(
                "Weltkatalog derzeit nicht verfügbar."
            ) from exc


class PostgresVehicleCatalogue(SqliteVehicleCatalogue):
    """Read immutable vehicle offers from PostgreSQL/Supabase."""

    def __init__(
        self, database_url: str, schema: str = "vehicle_catalogue"
    ) -> None:
        self.database_url = database_url
        self.schema = require_schema_name(schema)

    def list_models(self) -> tuple[VehicleModel, ...]:
        """Validate the migrated catalogue and project complete offers."""
        try:
            conninfo = _catalogue_conninfo(self.database_url, self.schema)
            with psycopg.connect(
                conninfo,
                autocommit=True,
                prepare_threshold=None,
            ) as raw:
                raw.execute(
                    cast(Any, f"SET search_path TO {self.schema}, public")
                )
                raw.execute(
                    "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ "
                    "READ ONLY"
                )
                adapter = PostgresConnectionAdapter(raw)
                try:
                    version = adapter.execute(
                        "SELECT value FROM catalog_metadata "
                        "WHERE key='schema_version'"
                    ).fetchone()
                    if version is None or version[0] != "2.2.0":
                        raise ValueError("Unsupported catalogue schema")
                    capabilities = read_transport_capabilities(
                        cast(Any, adapter)
                    )
                    models = tuple(
                        self._read_model(
                            cast(Any, row),
                            capabilities.get(row["id"], ()),
                        )
                        for row in adapter.execute(QUERY)
                    )
                    if not models:
                        raise ValueError("Empty catalogue")
                    return models
                finally:
                    raw.execute("ROLLBACK")
        except (psycopg.Error, ValueError, TypeError, KeyError) as exc:
            LOGGER.error(
                "Vehicle catalogue unavailable",
                extra={
                    "event": "catalogue.error",
                    "data": {"backend": "postgres", "error": str(exc)},
                },
            )
            raise CatalogueError(
                "Fahrzeugkatalog derzeit nicht verfügbar."
            ) from exc
