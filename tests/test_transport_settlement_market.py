"""Settlement effects at the city-market boundary."""

from dataclasses import replace
from unittest.mock import patch

from app.domain.errors import CatalogueError
from tests.support.game_clock import set_game_clock


async def test_arrival_activates_city_and_preserves_historical_terms(
    synthetic_game_context,
    synthetic_game,
):
    offer = next(
        item
        for item in synthetic_game.list_contracts()
        if item.destination.city.city_uid != item.origin.city.city_uid
    )
    build_trip = synthetic_game.transport_dispatch.build_trip

    def historical_trip(*args):
        trip = build_trip(*args)
        return replace(
            trip,
            contract=replace(
                trip.contract,
                market_model="nhm_v1",
                market_context=None,
                payload_band="heavy",
            ),
        )

    with patch.object(
        type(synthetic_game.transport_dispatch),
        "build_trip",
        lambda self, *args: historical_trip(*args),
    ):
        trip = await synthetic_game.dispatch(offer.id, "truck_01")
    set_game_clock(synthetic_game, lambda: trip.arrives_at + 1)
    with patch.object(
        synthetic_game_context.catalogue,
        "list_models",
        side_effect=CatalogueError("offline"),
    ):
        assert synthetic_game.reconcile_arrival()
        assert not synthetic_game.reconcile_arrival()
    settled = synthetic_game.state_repository.list_transports()[0]
    assert settled.contract == trip.contract
    assert settled.payout_eur == trip.payout_eur
    assert synthetic_game.get_vehicle("truck_01").location == trip.destination
    assert synthetic_game.list_contracts() == []
