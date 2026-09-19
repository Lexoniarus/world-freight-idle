"""Explicitly fictional economic defaults, separate from real world data."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models import CargoType

STANDARD_RATE = 0.18


@dataclass(frozen=True, slots=True)
class PayloadBand:
    """Simulated shipment class, bounded by its smallest vehicle payload."""

    name: str
    maximum_tons: float


def build_payload_bands(
    capacities: Sequence[float],
) -> tuple[PayloadBand, ...]:
    """Cover every catalogue payload without assuming fixed truck sizes."""
    if not capacities or any(
        not math.isfinite(value) or value < 0.01 for value in capacities
    ):
        raise ValueError("Payload capacities must be finite and >= 0.01 t")
    bands = []
    for name, lower, upper in (
        ("light", 0, 3.5),
        ("medium", 3.5, 12),
        ("heavy", 12, math.inf),
    ):
        members = [value for value in capacities if lower < value <= upper]
        if members:
            bands.append(PayloadBand(name, min(members)))
    return tuple(bands)


LEGACY_CARGO_TYPES = (
    CargoType("Automotive-Komponenten", 8.0, 24.0, 0.21),
    CargoType("Maschinenbauteile", 8.0, 22.0, 0.19),
    CargoType("Elektronik", 4.0, 16.0, 0.25),
    CargoType("Verpackte Lebensmittel", 8.0, 24.0, 0.16),
    CargoType("Konsumgüter", 7.0, 23.0, 0.17),
)
