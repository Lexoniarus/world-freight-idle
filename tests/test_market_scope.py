"""City market selection, coverage and immutable materialization behavior."""

from app.services.gameplay.fleet import build_owned_vehicle
from app.services.market.scope import MarketScopeResolver


def test_city_scope_uses_only_distinct_idle_city_identities(city_market):
    market, owned, _, world, model = city_market
    scope = MarketScopeResolver(world)
    other = build_owned_vehicle(model, "other", owned.location)
    busy = build_owned_vehicle(model, "busy", owned.location)
    busy.start_trip()
    assert scope.resolve((owned, other, busy)) == (
        owned.location.city.city_uid,
    )
    assert scope.resolve((busy,)) == ()
    destination = world.read().facilities[-1].location_snapshot()
    other.reposition_within_city(owned.location)
    other.start_trip()
    other.arrive(destination)
    assert len(scope.resolve((owned, other))) == 2
    # Same city name is not a shared identity.
    assert other.location is not None
    assert other.location.city.name == owned.location.city.name
    owned._location = None
    assert scope.resolve((owned,)) == (
        world.read().facilities[0].address.city.city_uid,
    )
