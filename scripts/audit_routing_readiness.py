"""Inspect routing locally or explicitly prewarm bounded provider work."""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_game_runtime, build_routing_audit  # noqa: E402
from app.config import Settings  # noqa: E402
from app.services.routing_inventory import routing_inventory  # noqa: E402
from app.tracing import background_trace  # noqa: E402


class RequestBudgetExceeded(RuntimeError):
    """Stop before sending a request beyond the explicit run budget."""


async def run(args: argparse.Namespace) -> None:
    """Compose the runtime and execute only explicitly requested prewarm."""
    settings = Settings.from_env()
    public = settings.valhalla_url == "https://valhalla1.openstreetmap.de"
    if args.prewarm and public:
        print(
            "WARNING: public Valhalla is for small development checks.",
            file=sys.stderr,
        )
        if not args.allow_public_endpoint:
            raise ValueError("Prewarm requires --allow-public-endpoint.")
    if args.request_limit < 1:
        raise ValueError("Request limit must be positive.")
    requests = 0

    async def count_request(request: httpx.Request) -> None:
        """Count every external request, including locate and geocoding."""
        nonlocal requests
        if requests >= args.request_limit:
            raise RequestBudgetExceeded(
                "Request budget exhausted; resume later."
            )
        requests += 1

    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        event_hooks={"request": [count_request]},
    ) as client:
        runtime = build_game_runtime(settings, client)
        world = runtime.world.read()
        runtime.catalogue.list_models()
        assert runtime.readiness is not None
        pairs = tuple(routing_inventory(world, args.city))
        if args.prewarm:
            try:
                with background_trace("cli-routing-prewarm"):
                    for origin, destination in pairs:
                        await runtime.readiness.prepare(origin, destination)
            except RequestBudgetExceeded as error:
                print(str(error), file=sys.stderr)
        focused = tuple(
            f.facility_uid
            for f in world.facilities
            if args.city
            and f.address.city.name.casefold() == args.city.casefold()
        )
        report = build_routing_audit(runtime).report(focused)
        report["facility_inventory"] = {
            "total": len(world.facilities),
            "catalogue_routable": sum(
                f.is_routable() for f in world.facilities
            ),
            "stored_anchor_results": sum(
                row["count"] for row in report["anchors"]
            ),
        }
        report["relevant_relations"] = len(pairs)
        report["current_relations"] = dict(
            Counter(
                relation.status
                if (relation := runtime.readiness.current(*pair))
                else "unchecked"
                for pair in pairs
            )
        )
        report["provider_requests"] = requests
        print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    """Parse an explicit report or bounded prewarm operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--prewarm", action="store_true")
    parser.add_argument("--request-limit", type=int, default=100)
    parser.add_argument("--allow-public-endpoint", action="store_true")
    parser.add_argument("--city")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
