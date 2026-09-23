"""Coherent typed transport setup for lifecycle tests."""

from dataclasses import replace

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
        offer = replace(offer, tons=tons)
    vehicle = game.state_repository.list_vehicles()[0]
    vehicle.start_trip()
    trip = ActiveTransport(
        transport_id,
        vehicle.id,
        offer,
        offer.origin,
        offer.destination,
        RouteSnapshot(((13, 52), (9, 53)), 400, 100, "fixture"),
        departed_at,
        arrives_at,
        payout,
        200,
    )
    with game.unit_of_work.transaction():
        game.state_repository.save_vehicle(vehicle)
        game.state_repository.save_transport(trip)
        game.state_repository.remove_offer(offer.id)
    return trip
