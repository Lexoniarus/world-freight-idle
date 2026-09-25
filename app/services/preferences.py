"""Validated account cosmetics with an explicit mutation boundary."""

import logging
from dataclasses import dataclass

from app.domain.company_colors import COMPANY_COLORS, player_color
from app.domain.preferences import AccountPreferences, PreferenceStore

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PreferenceService:
    """Resolve and change account color through an injected store."""

    store: PreferenceStore

    def read(self, user_id: str) -> AccountPreferences:
        """Resolve the original account color fallback."""
        return AccountPreferences(
            self.store.color(user_id) or player_color(user_id)
        )

    def update(self, user_id: str, color: str) -> AccountPreferences:
        """Validate a curated color and save it atomically for one account."""
        if color not in COMPANY_COLORS:
            raise ValueError("Bitte eine Farbe aus der Firmenpalette wählen.")
        with self.store.transaction():
            self.store.save_color(user_id, color)
        LOGGER.info(
            "Company color updated", extra={"event": "account.color_updated"}
        )
        return AccountPreferences(color)
