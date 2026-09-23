"""Explicitly fictional economic defaults, separate from real world data."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

STANDARD_RATE = 0.18
ENERGY_RESERVE_FRACTION = 0.1
DIESEL_STOP_MINUTES = 10.0


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
