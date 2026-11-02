"""Checksummed private rollback archives for market-stock repair."""

import json
import sqlite3
from hashlib import sha256
from pathlib import Path

from app.domain.errors import PersistenceError
from app.domain.market_stock_repair import (
    MarketStockRemoval,
    MarketStockRepairPlan,
)
from app.repositories.market_stock_repair.validation import read_selected_rows


class MarketStockRepairArchive:
    """Write and verify the exact rows affected by one repair plan."""

    def write_repair_archive(
        self,
        source: sqlite3.Connection,
        plan: MarketStockRepairPlan,
        archive: Path,
    ) -> None:
        """Archive every removed or reset row with a payload checksum."""
        records = [
            self._checked_record(self._offer_payload(source, removal))
            for removal in plan.removals
        ]
        records.extend(
            self._checked_record(self._player_payload(source, user_id))
            for user_id in sorted({item.user_id for item in plan.removals})
        )
        archive.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for record in records
            ),
            encoding="utf-8",
            newline="\n",
        )
        self.verify_archive(archive)

    def verify_archive(self, archive: Path) -> None:
        """Reject any archive record whose canonical checksum differs."""
        for line in archive.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            checksum = record.pop("sha256")
            if checksum != self._checksum(record):
                raise PersistenceError("Marktreparaturarchiv abweichend.")

    def _offer_payload(
        self,
        source: sqlite3.Connection,
        removal: MarketStockRemoval,
    ) -> dict[str, object]:
        """Collect all rows owned by one removable private offer."""
        return {
            "repair_version": 1,
            "kind": "offer",
            "user_id": removal.user_id,
            "contract_id": removal.contract_id,
            "tables": {
                table: read_selected_rows(
                    source,
                    table,
                    "user_id=? AND contract_id=?",
                    (removal.user_id, removal.contract_id),
                )
                for table in (
                    "contract_offers",
                    "market_offer_templates",
                    "offer_route_references",
                )
            },
        }

    def _player_payload(
        self,
        source: sqlite3.Connection,
        user_id: str,
    ) -> dict[str, object]:
        """Collect scheduler rows reset for one affected player."""
        return {
            "repair_version": 1,
            "kind": "player_reset",
            "user_id": user_id,
            "tables": {
                table: read_selected_rows(
                    source,
                    table,
                    "user_id=?",
                    (user_id,),
                )
                for table in (
                    "market_stock_pending",
                    "market_stock_cursors",
                    "market_preparations",
                    "market_coverage",
                )
            },
        }

    def _checked_record(self, payload: dict[str, object]) -> dict[str, object]:
        """Attach a canonical checksum without logging archive contents."""
        return {**payload, "sha256": self._checksum(payload)}

    @staticmethod
    def _checksum(payload: dict[str, object]) -> str:
        """Hash one canonical JSON archive payload."""
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()
