"""Derive reproducible market choices without mutable random state."""

from dataclasses import dataclass
from hashlib import sha256
from math import log


@dataclass(frozen=True, slots=True)
class DeterministicMarketRandom:
    """Map stable market context to independent weighted draws."""

    version: str = "market-stock-v1"

    def fraction(self, *parts: object) -> float:
        """Return a stable value strictly between zero and one."""
        payload = "\x1f".join((self.version, *(str(part) for part in parts)))
        value = int.from_bytes(sha256(payload.encode()).digest()[:8], "big")
        return (value + 1) / (2**64 + 1)

    def weighted_index(
        self,
        identities: tuple[str, ...],
        weights: tuple[float, ...],
        *context: object,
    ) -> int:
        """Choose reproducibly with an order-independent weighted race."""
        if not identities or len(identities) != len(weights):
            raise ValueError("Weighted market choices must align.")
        if len(set(identities)) != len(identities) or any(
            weight <= 0 for weight in weights
        ):
            raise ValueError("Weighted market choices must be unique.")
        return min(
            range(len(identities)),
            key=lambda index: (
                -log(
                    self.fraction(
                        *context,
                        identities[index],
                    )
                )
                / weights[index],
                identities[index],
            ),
        )
