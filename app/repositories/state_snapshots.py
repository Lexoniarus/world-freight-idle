"""Versioned historical document encoding at the persistence boundary."""

import json
from typing import Any

from app.domain.errors import PersistenceError


def encode_snapshot(kind: str, data: dict[str, Any]) -> str:
    """Write explicit document identity/version and reject non-JSON numbers."""
    try:
        return json.dumps(
            {
                "version": 2 if kind == "transport" else 1,
                "kind": kind,
                "data": data,
            },
            allow_nan=False,
        )
    except (ValueError, TypeError) as exc:
        raise PersistenceError("Ungültiger Spielstand-Snapshot.") from exc


def decode_snapshot(kind: str, encoded: str) -> dict[str, Any]:
    """Reject unknown versions and malformed document envelopes."""
    try:
        value = json.loads(encoded)
        if (
            not isinstance(value, dict)
            or type(value.get("version")) is not int
            or value["version"] != (2 if kind == "transport" else 1)
            or value.get("kind") != kind
            or not isinstance(value.get("data"), dict)
        ):
            raise ValueError("Snapshot envelope differs")
        return value["data"]
    except (ValueError, TypeError) as exc:
        raise PersistenceError("Spielstand-Snapshot nicht lesbar.") from exc
