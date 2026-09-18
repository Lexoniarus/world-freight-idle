from app.seed_data import CARGO_TYPES
from app.services.pricing import PricingService


def test_pricing_quote_uses_distance_and_cargo_rate():
    service = PricingService(CARGO_TYPES)
    quote = service.quote("Elektronik", 10, 100)
    assert quote.payout_eur == 470
    assert quote.operating_cost_eur == 142
    assert quote.profit_eur == 328
