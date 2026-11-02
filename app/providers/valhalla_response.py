"""Validation and normalization of Valhalla provider responses."""

import json
from typing import Any

import httpx

from app.domain.errors import RoutingError, RoutingFailureCategory
from app.domain.transports import RouteSnapshot
from app.providers.validation import validate_route

_ENDPOINT_UNREACHABLE_CODES = frozenset({171, 441})
_NO_PATH_CODES = frozenset({170, 442})
_DISTANCE_LIMIT_CODES = frozenset({154})


def decode_polyline6(encoded: str) -> list[list[float]]:
    """Decode Valhalla polyline6 into GeoJSON coordinates."""
    coordinates: list[list[float]] = []
    index = 0
    latitude = 0
    longitude = 0
    factor = 1_000_000.0
    while index < len(encoded):
        deltas: list[int] = []
        for _ in range(2):
            result = 0
            shift = 0
            while True:
                if index >= len(encoded):
                    error = RoutingError("Ungültige Routing-Polyline.")
                    error.category = "invalid_response"
                    error.retryable = False
                    raise error
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            deltas.append(delta)
        latitude += deltas[0]
        longitude += deltas[1]
        coordinates.append([longitude / factor, latitude / factor])
    return coordinates


class ValhallaResponseParser:
    """Translate HTTP payloads into stable routing-domain results."""

    @staticmethod
    def provider_error(response: httpx.Response) -> RoutingError:
        """Translate one Valhalla HTTP failure into stable categories."""
        provider_code: int | None = None
        provider_message = response.text[:200] or None
        try:
            payload = response.json()
        except (ValueError, UnicodeError):
            payload = None
        if isinstance(payload, dict):
            raw_code = payload.get("error_code")
            if isinstance(raw_code, int) and not isinstance(raw_code, bool):
                provider_code = raw_code
            raw_message = payload.get("error")
            if isinstance(raw_message, str) and raw_message.strip():
                provider_message = raw_message.strip()

        normalized_message = (provider_message or "").casefold()
        category: RoutingFailureCategory
        message: str
        retryable = False
        if provider_code in _ENDPOINT_UNREACHABLE_CODES or any(
            marker in normalized_message
            for marker in (
                "no suitable edges near location",
                "no data found for location",
                "location is unreachable",
            )
        ):
            category = "endpoint_unreachable"
            message = "Routing-Endpunkt ist im Straßennetz nicht erreichbar."
        elif provider_code in _NO_PATH_CODES or any(
            marker in normalized_message
            for marker in (
                "no path could be found for input",
                "unconnected regions",
            )
        ):
            category = "no_path"
            message = "Zwischen den Endpunkten existiert kein Straßenpfad."
        elif provider_code in _DISTANCE_LIMIT_CODES or (
            "path distance exceeds the max distance limit"
            in normalized_message
        ):
            category = "distance_limit"
            message = "Die Straßenroute überschreitet das Distanzlimit."
        else:
            category = "provider_unavailable"
            message = "Routing-Anbieter nicht verfügbar."
            retryable = response.status_code in {408, 429} or (
                response.status_code >= 500
            )
        error = RoutingError(message)
        error.category = category
        error.provider_code = provider_code
        error.provider_message = provider_message
        error.retryable = retryable
        return error

    @staticmethod
    def response_payload(response: httpx.Response) -> dict[str, Any]:
        """Decode one successful response with bounded evidence."""
        try:
            payload = response.json()
        except (ValueError, UnicodeError) as exc:
            error = RoutingError(
                "Routing-Anbieter lieferte eine ungültige Antwort."
            )
            error.category = "invalid_response"
            error.provider_message = response.text[:200] or None
            error.retryable = False
            raise error from exc
        if not isinstance(payload, dict):
            error = RoutingError(
                "Routing-Anbieter lieferte eine ungültige Antwort."
            )
            error.category = "invalid_response"
            error.provider_message = response.text[:200] or None
            error.retryable = False
            raise error
        return payload

    @staticmethod
    def extract_route(data: dict[str, Any]) -> RouteSnapshot:
        """Normalize Valhalla JSON into the domain route representation."""
        try:
            trip = data["trip"]
            if not isinstance(trip, dict):
                raise ValueError("Expected a trip object")
            summary = trip["summary"]
            coordinates: list[list[float]] = []
            for leg in trip["legs"]:
                if not isinstance(leg, dict):
                    raise ValueError("Expected a leg object")
                shape = leg.get("shape")
                if (
                    isinstance(shape, dict)
                    and shape.get("type") == "LineString"
                ):
                    leg_coordinates = shape["coordinates"]
                elif isinstance(shape, str):
                    leg_coordinates = decode_polyline6(shape)
                else:
                    error = RoutingError(
                        "Routing-Anbieter lieferte keine verwertbare "
                        "Routengeometrie."
                    )
                    error.category = "invalid_response"
                    error.retryable = False
                    raise error
                if (
                    coordinates
                    and leg_coordinates
                    and coordinates[-1] == leg_coordinates[0]
                ):
                    leg_coordinates = leg_coordinates[1:]
                coordinates.extend(leg_coordinates)
        except (KeyError, TypeError, ValueError) as exc:
            preview = json.dumps(data, ensure_ascii=False)[:400]
            error = RoutingError(
                "Routing-Anbieter lieferte eine unerwartete Antwort."
            )
            error.category = "invalid_response"
            error.provider_message = preview
            error.retryable = False
            raise error from exc
        if len(coordinates) < 2:
            error = RoutingError("Route enthält zu wenige Punkte.")
            error.category = "invalid_response"
            error.retryable = False
            raise error
        if any(isinstance(summary[key], bool) for key in ("length", "time")):
            raise ValueError("Invalid route metric type")
        return validate_route(
            {
                "distance_km": float(summary["length"]),
                "duration_seconds": float(summary["time"]),
                "route_geojson": {
                    "type": "LineString",
                    "coordinates": coordinates,
                },
                "provider": "Valhalla / OpenStreetMap (truck)",
            }
        )
