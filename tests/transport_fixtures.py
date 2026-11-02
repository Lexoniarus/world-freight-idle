"""Coherent typed transport setup for lifecycle tests."""

from dataclasses import replace
from typing import overload

from app.composition.player import PlayerServiceContext
from app.domain.contracts import ContractOffer, HistoricalContractSnapshot
from app.domain.journeys import unmetered_journey
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.services.gameplay.player_game import PlayerGameFacade
from tests.support.game_service import FixturePlayerGameFacade


@overload
def add_transport(
    synthetic_game: FixturePlayerGameFacade,
    payout: int = 1000,
    departed_at: float = 1,
    arrives_at: float = 2,
    tons: float | None = None,
    transport_id: str = "fixture-trip",
    *,
    context: None = None,
) -> ActiveTransport: ...


@overload
def add_transport(
    synthetic_game: PlayerGameFacade,
    payout: int = 1000,
    departed_at: float = 1,
    arrives_at: float = 2,
    tons: float | None = None,
    transport_id: str = "fixture-trip",
    *,
    context: PlayerServiceContext,
) -> ActiveTransport: ...


def add_transport(
    synthetic_game: PlayerGameFacade,
    payout: int = 1000,
    departed_at: float = 1,
    arrives_at: float = 2,
    tons: float | None = None,
    transport_id: str = "fixture-trip",
    *,
    context: PlayerServiceContext | None = None,
) -> ActiveTransport:
    """Reserve a real owned vehicle and persist a complete test snapshot."""
    if context is None:
        assert isinstance(synthetic_game, FixturePlayerGameFacade)
        lifecycle = synthetic_game.market_lifecycle
        repository = synthetic_game.state_repository
        unit_of_work = synthetic_game.unit_of_work
    else:
        lifecycle = context.lifecycle
        repository = context.state_repository
        unit_of_work = context.unit_of_work
    market = lifecycle.generation
    market_scope = lifecycle.scope
    owned = repository.list_vehicles()
    fleet = market.candidates.resolve_fleet(owned)
    candidates = market.candidates.build(market_scope.resolve(owned), fleet)
    candidate = next(
        item
        for item in candidates
        if item.trade.origin.facility_uid == owned[0].facility_uid
    )
    offer = ContractOffer.from_snapshot(
        market.contract_factory.build(candidate, synthetic_game.now())
    )
    offer = replace(offer, created_at=0, expires_at=max(arrives_at, 10))
    if tons is not None:
        market_context = offer.market_context
        assert market_context is not None
        market_context = replace(
            market_context,
            generated_capacity_tons=max(
                market_context.generated_capacity_tons, tons
            ),
            cargo_value_eur=round(tons * market_context.cargo_value_eur_per_t),
        )
        offer = replace(offer, tons=tons, market_context=market_context)
    vehicle = repository.list_vehicles()[0]
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
    with unit_of_work.transaction():
        repository.save_vehicle(vehicle)
        repository.save_transport(trip)
        repository.remove_offer(offer.id)
    return trip
