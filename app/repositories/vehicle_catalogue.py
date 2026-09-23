"""Read-only SQLite adapter for the separately shipped vehicle catalogue."""

import logging
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

from app.domain.energy import EnergyKind, EnergyProfile, EnergyUnit
from app.domain.errors import CatalogueError
from app.domain.vehicles import VehicleImage, VehicleModel
from app.simulation import DIESEL_STOP_MINUTES, ENERGY_RESERVE_FRACTION

LOGGER = logging.getLogger(__name__)
QUERY = """
SELECT m.vehicle_id AS id,
       maker.name || ' ' || m.model || ' ' || m.variant AS name,
       maker.name AS manufacturer, m.powertrain, m.top_speed_kmh,
       m.consumption_value, m.consumption_unit,
       m.fuel_tank_capacity_l, m.fuel_tank_capacity_kg,
       m.battery_usable_kwh, b.energy_stop_minutes_game,
       b.payload_t_game AS capacity_tons,
       b.purchase_price_eur_game AS price_eur,
       b.operating_cost_eur_per_km_game AS operating_cost_eur_per_km,
       b.unlock_reputation_game AS unlock_reputation,
       i.direct_image_url AS image_url, s.source_url AS image_source_url,
       i.author AS image_author, l.license_name AS image_license_name,
       l.license_url AS image_license_url,
       i.attribution_text AS image_attribution, i.image_scope AS image_scope
FROM vehicle_models m
LEFT JOIN manufacturers maker USING (manufacturer_id)
LEFT JOIN vehicle_balance b USING (vehicle_id)
LEFT JOIN vehicle_images i ON i.image_id = (
    SELECT image_id FROM vehicle_images candidate
    WHERE candidate.vehicle_id = m.vehicle_id
      AND candidate.verification_status = 'verified'
    ORDER BY candidate.is_primary DESC, candidate.image_id LIMIT 1
)
LEFT JOIN sources s ON s.source_id = i.source_id
LEFT JOIN licenses l ON l.license_id = i.license_id
ORDER BY b.purchase_price_eur_game, m.vehicle_id
"""


class SqliteVehicleCatalogue:
    """Open an independent read-only connection for each catalogue read."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_models(self) -> tuple[VehicleModel, ...]:
        """Validate the reference schema and project complete offers."""
        try:
            uri = self.path.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                version = connection.execute(
                    "SELECT value FROM catalog_metadata "
                    "WHERE key = 'schema_version'"
                ).fetchone()
                if not version or version[0] != "2.1.0":
                    raise ValueError("Unsupported catalogue schema")
                if connection.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("Broken catalogue references")
                models = tuple(
                    self._read_model(row) for row in connection.execute(QUERY)
                )
                if not models:
                    raise ValueError("Empty catalogue")
                return models
        except (sqlite3.Error, ValueError, TypeError, OSError) as exc:
            LOGGER.error(
                "Vehicle catalogue unavailable",
                extra={
                    "event": "catalogue.error",
                    "data": {"error": str(exc)},
                },
            )
            raise CatalogueError(
                "Fahrzeugkatalog derzeit nicht verfügbar."
            ) from exc

    def _read_model(self, row: sqlite3.Row) -> VehicleModel:
        """Reject incomplete or invalid gameplay values before projection."""
        values = dict(row)
        energy = read_energy_profile(values)
        image_values = {
            key.removeprefix("image_"): values.pop(key)
            for key in list(values)
            if key.startswith("image_")
        }
        for key in ("id", "name", "manufacturer", "powertrain"):
            if not isinstance(values[key], str) or not values[key].strip():
                raise ValueError("Invalid catalogue text")
        for key in ("price_eur", "unlock_reputation"):
            if type(values[key]) is not int or values[key] < 0:
                raise ValueError("Invalid catalogue integer")
        for key in ("capacity_tons", "operating_cost_eur_per_km"):
            value = values[key]
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Invalid catalogue number")
        if (
            values["capacity_tons"] <= 0
            or values["operating_cost_eur_per_km"] < 0
        ):
            raise ValueError("Invalid catalogue range")
        return VehicleModel(
            **values, energy=energy, image=self._read_image(image_values)
        )

    def _read_image(self, values: dict) -> VehicleImage | None:
        """Use only complete HTTPS Wikimedia/Creative Commons records."""
        if not values["url"]:
            return None
        valid = all(
            isinstance(value, str) and value.strip()
            for value in values.values()
        )
        hosts = {
            "url": "upload.wikimedia.org",
            "source_url": "commons.wikimedia.org",
            "license_url": "creativecommons.org",
        }
        for key, host in hosts.items():
            try:
                url = urlsplit(values[key] or "")
                valid = valid and url.scheme == "https" and url.netloc == host
            except ValueError:
                valid = False
        if not valid:
            LOGGER.warning(
                "Invalid vehicle image metadata",
                extra={"event": "catalogue.image_invalid"},
            )
            return None
        return VehicleImage(**values)


def read_energy_profile(values: dict) -> EnergyProfile:
    """Extract and validate energy columns from one catalogue record."""
    specification: dict[str, tuple[EnergyKind, EnergyUnit, str]] = {
        "combustion": ("diesel", "l", "fuel_tank_capacity_l"),
        "gas": ("gas", "kg", "fuel_tank_capacity_kg"),
        "battery_electric": ("electric", "kWh", "battery_usable_kwh"),
    }
    if values["powertrain"] not in specification:
        raise ValueError("Unsupported vehicle energy kind.")
    kind, unit, capacity_field = specification[values["powertrain"]]
    capacities = {
        key: values.pop(key)
        for key in (
            "fuel_tank_capacity_l",
            "fuel_tank_capacity_kg",
            "battery_usable_kwh",
        )
    }
    if any(
        value is not None
        for key, value in capacities.items()
        if key != capacity_field
    ):
        raise ValueError("Conflicting energy capacities.")
    if values.pop("consumption_unit") != unit + "/100km":
        raise ValueError("Consumption unit differs from energy kind.")
    stop = values.pop("energy_stop_minutes_game")
    return EnergyProfile(
        kind=kind,
        unit=unit,
        capacity=capacities[capacity_field],
        consumption_per_100km=values.pop("consumption_value"),
        stop_minutes=DIESEL_STOP_MINUTES if kind == "diesel" else stop,
        reserve_fraction=ENERGY_RESERVE_FRACTION,
    )
