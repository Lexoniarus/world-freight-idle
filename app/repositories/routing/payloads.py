"""Canonical decoding of cached provider route payloads."""

import json

from app.domain.routing_readiness import RoutePayload


def decode_route_payload(document: str) -> RoutePayload | None:
    """Validate canonical provider geometry independently of availability."""
    try:
        values = json.loads(document)
        values["coordinates"] = tuple(
            tuple(point) for point in values["coordinates"]
        )
        return RoutePayload(**values)
    except (ValueError, KeyError, TypeError):
        return None
