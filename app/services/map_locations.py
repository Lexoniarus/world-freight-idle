"""Read-only map projection over the shared geocoding provider."""

import logging
import math
from typing import Any

from app.domain.errors import GeocodingError
from app.domain.models import Hub
from app.domain.ports import Geocoder

LOGGER = logging.getLogger(__name__)


class MapLocationService:
    """Resolve the fixed freight locations without fabricating coordinates."""

    def __init__(self, geocoder: Geocoder, hubs: tuple[Hub, ...]) -> None:
        self.geocoder = geocoder
        self.hubs = hubs

    async def list_hubs(self) -> list[dict[str, Any]]:
        """Return independent success/error states for each real location."""
        locations = []
        for hub in self.hubs:
            location = hub.to_dict()
            try:
                lat, lon, address = await self.geocoder.geocode(hub.address)
                if not (
                    math.isfinite(lat)
                    and math.isfinite(lon)
                    and -90 <= lat <= 90
                    and -180 <= lon <= 180
                ):
                    raise ValueError("Invalid map coordinates")
                location.update(
                    lat=lat,
                    lon=lon,
                    geocoded_address=address,
                    resolution_status="resolved",
                )
            except (GeocodingError, ValueError, KeyError):
                LOGGER.warning(
                    "Map location unavailable",
                    exc_info=True,
                    extra={
                        "event": "map.location_failed",
                        "data": {"hub_id": hub.id},
                    },
                )
                location.update(
                    lat=None,
                    lon=None,
                    resolution_status="unavailable",
                )
            locations.append(location)
        return locations
