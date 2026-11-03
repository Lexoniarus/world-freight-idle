"""Historical contract snapshot compatibility at the mapping boundary."""

from dataclasses import asdict

from app.domain.contracts import HistoricalContractSnapshot
from app.repositories.snapshot_mapping import load_historical_contract


def test_historical_v2_and_missing_context_roundtrip_without_catalogue(
    synthetic_game,
):
    offer = synthetic_game.list_contracts()[0]
    historical = HistoricalContractSnapshot.from_offer(offer)
    assert load_historical_contract(asdict(historical)) == historical
    old = asdict(historical)
    old.pop("market_context")
    old["market_model"] = "nhm_v1"
    restored = load_historical_contract(old)
    assert restored.market_context is None
    assert restored.tons == offer.tons
