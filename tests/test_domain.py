from dataclasses import asdict

from app.domain.models import Contract, Hub, PriceQuote, RouteResult


def test_hub_reference_fields():
    hub = Hub("x", "Berlin", "Hub", "Address", "DE")
    assert asdict(hub)["address"] == "Address"


def test_minimal_contract_fields():
    contract = Contract("id", "a", "b", "s", "c", "cargo", 12, 1, 2)
    assert asdict(contract)["tons"] == 12


def test_route_result_fields():
    route = RouteResult(10, 20, {"type": "LineString", "coordinates": []}, "x")
    assert asdict(route)["provider"] == "x"


def test_price_quote_values():
    quote = PriceQuote(100, 70, 30)
    assert asdict(quote) == {
        "payout_eur": 100,
        "operating_cost_eur": 70,
        "profit_eur": 30,
    }
