"""Small invariant checks shared by domain objects."""

import math


def require_finite(value: object, name: str, minimum: float = 0) -> None:
    """Reject nonnumeric, nonfinite and out-of-range domain values."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < minimum
    ):
        raise ValueError(f"{name} must be finite and >= {minimum}.")


def require_integer(value: object, name: str) -> None:
    """Require whole non-negative game units without coercion."""
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")


def require_identity(value: object, name: str) -> None:
    """Reject missing identity instead of inventing a replacement."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty.")
