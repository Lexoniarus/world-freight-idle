import random

from app.seed_data import (
    CARGO_TYPES,
    FICTIONAL_CONSIGNEES,
    FICTIONAL_SHIPPERS,
    HUBS,
)
from app.services.market import MarketGenerator


def make_market(seed=3):
    return MarketGenerator(
        HUBS,
        CARGO_TYPES,
        FICTIONAL_SHIPPERS,
        FICTIONAL_CONSIGNEES,
        random.Random(seed),
    )


def test_market_generate_guarantees_origin_and_real_addresses_are_external():
    market = make_market()
    contracts = market.generate(1000.0, [HUBS[0].id], 4)
    assert len(contracts) == 4
    assert contracts[0]["origin_hub_id"] == HUBS[0].id
    assert all(
        c["origin_hub_id"] != c["destination_hub_id"] for c in contracts
    )


def test_build_contract_has_expiry_and_valid_cargo():
    market = make_market()
    contract = market._build_contract(HUBS[0].id, 1000.0)
    assert contract.expires_at == 1000.0 + 21600
    assert contract.cargo in {cargo.name for cargo in CARGO_TYPES}
    assert 0 < contract.tons <= 24


def test_market_generate_returns_empty_without_hubs():
    market = MarketGenerator(
        (),
        CARGO_TYPES,
        FICTIONAL_SHIPPERS,
        FICTIONAL_CONSIGNEES,
        random.Random(1),
    )
    assert market.generate(1.0, []) == []
