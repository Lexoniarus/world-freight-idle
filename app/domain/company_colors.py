"""Account cosmetics and the unchanged deterministic legacy fallback."""

import colorsys
import hashlib

COMPANY_COLORS = (
    "#e45756",
    "#4c78a8",
    "#2a9d8f",
    "#f6bc43",
    "#9c6ade",
    "#e87524",
    "#d45087",
    "#477a3c",
    "#805c46",
    "#526d82",
)


def player_color(user_id: str) -> str:
    """Derive a stable, saturated map color from a persistent user ID."""
    digest = hashlib.sha256(user_id.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65535
    red, green, blue = colorsys.hls_to_rgb(hue, 0.52, 0.70)
    channels = (round(red * 255), round(green * 255), round(blue * 255))
    return "#" + "".join(f"{channel:02x}" for channel in channels)
