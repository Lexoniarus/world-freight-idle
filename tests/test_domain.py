from app.domain.models import Contract, Hub, PriceQuote, RouteResult


def test_hub_to_dict():
    hub = Hub("x", "Berlin", "Hub", "Address", "DE")
    assert hub.to_dict()["address"] == "Address"


def test_contract_to_dict():
    contract = Contract("id", "a", "b", "s", "c", "cargo", 12, 1, 2)
    assert contract.to_dict()["tons"] == 12


def test_route_result_to_dict():
    route = RouteResult(10, 20, {"type": "LineString", "coordinates": []}, "x")
    assert route.to_dict()["provider"] == "x"


def test_price_quote_to_dict():
    quote = PriceQuote(100, 70, 30)
    assert quote.to_dict() == {
        "payout_eur": 100,
        "operating_cost_eur": 70,
        "profit_eur": 30,
    }
