"""Enumerate relevant global relations without fabricating a player fleet."""

from collections.abc import Iterator

from app.domain.world import WorldSnapshot
from app.services.trade_network import TradeNetwork


def routing_inventory(
    world: WorldSnapshot,
    city_name: str | None = None,
) -> Iterator[tuple[str, str]]:
    """Yield NHM trades and city approaches, never a global cross-product."""
    network = TradeNetwork(world.facilities)
    seen: set[tuple[str, str]] = set()
    for origin in world.facilities:
        if not origin.is_routable():
            continue
        if (
            city_name
            and origin.address.city.name.casefold() != city_name.casefold()
        ):
            continue
        trades = network.options_for(origin.facility_uid)
        for trade in trades:
            pair = origin.facility_uid, trade.destination.facility_uid
            if pair not in seen:
                seen.add(pair)
                yield pair
        if not trades:
            continue
        for start in world.facilities:
            if (
                start.is_routable()
                and start.address.city.city_uid == origin.address.city.city_uid
                and start.facility_uid != origin.facility_uid
            ):
                pair = start.facility_uid, origin.facility_uid
                if pair not in seen:
                    seen.add(pair)
                    yield pair
