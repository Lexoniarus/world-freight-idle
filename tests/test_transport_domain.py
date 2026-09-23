"""Transport invariants and transitional adapter behavior."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.domain.contracts import ContractOffer
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.repositories.transport_mapping import dump_transport, load_transport


def test_transport_lifecycle_rejects_invalid_and_duplicate_settlement(game):
    offer = ContractOffer.from_dict(
        [item.to_dict() for item in game.state_repository.list_offers()][0]
    )
    route = RouteSnapshot(((13.3, 52.5), (9.9, 53.5)), 300, 100, "fake")
    trip = ActiveTransport(
        "trip",
        "truck",
        offer,
        offer.origin,
        offer.destination,
        route,
        10,
        110,
        500,
        200,
    )
    assert not trip.is_due(109)
    assert trip.is_due(110)
    with pytest.raises(ValueError, match="not due"):
        trip.settle(109)
    settled = trip.settle(111)
    assert settled.status == "settled" and settled.settled_at == 111
    assert trip.status == "active"
    assert not settled.is_due(200)
    with pytest.raises(ValueError, match="not due"):
        settled.settle(200)
    with pytest.raises(FrozenInstanceError):
        setattr(trip, "payout_eur", 999)
    for changes in (
        {"id": ""},
        {"arrives_at": 10},
        {"payout_eur": -1},
        {"payout_eur": 1.5},
        {"departed_at": float("nan")},
        {"origin": offer.destination},
        {"status": "unknown"},
        {"settled_at": 111},
        {"status": "settled"},
        {"status": "settled", "settled_at": 109},
    ):
        with pytest.raises(ValueError):
            replace(trip, **changes)
    with pytest.raises(ValueError):
        trip.is_due(float("nan"))
    payload = dump_transport(trip)
    assert load_transport(payload) == trip
    assert payload["profit_eur"] == 300
    payload["route_geojson"] = {
        "type": "Feature",
        "geometry": payload["route_geojson"],
    }
    assert load_transport(payload) == trip
    payload["arrives_at"] = 9
    with pytest.raises(ValueError):
        load_transport(payload)


def test_route_snapshot_rejects_invalid_measurements_and_geometry():
    route = RouteSnapshot(((180, 90), (-180, -90)), 1, 1, "fake")
    assert len(route.coordinates) == 2
    for changes in (
        {"coordinates": ()},
        {"coordinates": [[0, 0], [1, 1]]},
        {"coordinates": ([0, 0], [1, 1])},
        {"coordinates": ((181, 1), (0, 0))},
        {"coordinates": ((0, 91), (0, 0))},
        {"coordinates": ((float("nan"), 1), (0, 0))},
        {"distance_km": 0},
        {"duration_seconds": -1},
        {"provider": ""},
    ):
        with pytest.raises(ValueError):
            replace(route, **changes)


def test_transport_settlement_keeps_saved_location_without_catalogue(game):
    from unittest.mock import patch

    from app.domain.errors import WorldCatalogueError
    from tests.transport_fixtures import add_transport

    trip = add_transport(game, payout=50)
    with patch.object(game.world, "read", side_effect=WorldCatalogueError()):
        assert game.reconcile_arrival()
        assert game.list_vehicles()[0]["hub"] == trip.destination.to_dict()
    player = game.state_repository.get_player()
    assert player is not None and player.cash == 175050
    assert not game.reconcile_arrival()
    assert game.state_repository.list_transports()[0].status == "settled"
