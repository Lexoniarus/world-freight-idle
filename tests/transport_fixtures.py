"""Coherent typed transport setup for lifecycle tests."""

from dataclasses import replace

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.journeys import unmetered_journey
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.services.game import GameService


def add_transport(
    game: GameService,
    payout: int = 1000,
    departed_at: float = 1,
    arrives_at: float = 2,
    tons: float | None = None,
    transport_id: str = "fixture-trip",
) -> ActiveTransport:
    """Reserve a real owned vehicle and persist a complete test snapshot."""
    game.refresh_market()
    offer = game.state_repository.list_offers()[0]
    offer = replace(offer, created_at=0, expires_at=max(arrives_at, 10))
    if tons is not None:
        context = offer.market_context
        assert context is not None
        context = replace(
            context,
            generated_capacity_tons=max(context.generated_capacity_tons, tons),
            cargo_value_eur=round(tons * context.cargo_value_eur_per_t),
        )
        offer = replace(offer, tons=tons, market_context=context)
    vehicle = game.state_repository.list_vehicles()[0]
    vehicle.reposition_within_city(offer.origin)
    vehicle.start_trip()
    trip = ActiveTransport(
        transport_id,
        vehicle.id,
        HistoricalContractSnapshot.from_offer(offer),
        offer.origin,
        offer.destination,
        RouteSnapshot(((13, 52), (9, 53)), 400, 100, "fixture"),
        departed_at,
        arrives_at,
        payout,
        200,
        journey=unmetered_journey(
            400,
            (arrives_at) - (departed_at),
        ),
    )
    with game.unit_of_work.transaction():
        game.state_repository.save_vehicle(vehicle)
        game.state_repository.save_transport(trip)
        game.state_repository.remove_offer(offer.id)
    return trip
