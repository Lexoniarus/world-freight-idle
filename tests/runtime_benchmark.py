"""Explicit performance acceptance on a new private copy, never live storage.

Run: python -m tests.runtime_benchmark SOURCE_DB NEW_OUTPUT_DIRECTORY
Uses deterministic provider fixtures in a separate preparation process.
"""

import asyncio
import json
import os
import platform
import secrets
import statistics
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path

import httpx

from app.launcher import stop_child
from app.repositories.accounts import AccountRepository
from app.repositories.database_backup import backup_database
from app.repositories.game_database import SqliteGameDatabase


async def main() -> None:
    source, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    original = sha256(source.read_bytes()).hexdigest()
    target = output / "benchmark.db"
    backup_database(source, target)
    database = SqliteGameDatabase(target)
    database.initialize()
    accounts = AccountRepository(database)
    with database.connect() as connection:
        owners = [
            r[0]
            for r in connection.execute(
                "SELECT user_id FROM player_states ORDER BY user_id"
            )
        ]
        vehicles = connection.execute(
            "SELECT COUNT(*) FROM owned_vehicles"
        ).fetchone()[0]
        templates_before = connection.execute(
            "SELECT COUNT(*) FROM market_templates"
        ).fetchone()[0]
    assert len(owners) == 3 and vehicles <= 35
    tokens = [secrets.token_urlsafe(32) for _ in owners]
    for owner, token in zip(owners, tokens):
        accounts.save_session(token, owner, 3600)
    env = {
        **os.environ,
        "DB_PATH": str(target),
        "HOST": "127.0.0.1",
        "PORT": "8027",
        "WFI_MANAGED_CHILD": "1",
        "LOG_LEVEL": "WARNING",
        "VALHALLA_URL": "https://routing.test",
    }
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    children = []
    try:
        with (output / "process.log").open("wb") as log:
            for args in (
                ("main.py", "--role", "runtime"),
                ("-m", "tests.browser_worker", str(target)),
            ):
                children.append(
                    await asyncio.create_subprocess_exec(
                        sys.executable,
                        *args,
                        env=env,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=log,
                        stderr=log,
                        creationflags=flags,
                    )
                )
            async with httpx.AsyncClient(
                base_url="http://127.0.0.1:8027", timeout=10
            ) as client:
                for attempt in range(150):
                    try:
                        response = await client.get("/api/v1/system/health")
                        response.raise_for_status()
                        break
                    except httpx.HTTPError:
                        await asyncio.sleep(0.1)
                else:
                    raise RuntimeError("Benchmark runtime did not start")
                # Exercise cold player state in fresh browser contexts first,
                # including any due settlement in the repaired profile.
                credentials = output / "browser-session.json"
                credentials.write_text(
                    json.dumps({"tokens": tokens, "output": str(output)}),
                    encoding="utf-8",
                )
                browser = await asyncio.create_subprocess_exec(
                    "node",
                    "tests/runtime_benchmark.mjs",
                    str(credentials),
                    stdout=log,
                    stderr=log,
                )
                assert await browser.wait() == 0
                browser_report = json.loads(
                    (output / "browser.json").read_text()
                )
                latencies: dict[str, list[float]] = {
                    key: []
                    for key in (
                        "runtime",
                        "map/traffic?representation=summary",
                        "contracts",
                        "system/health",
                    )
                }
                sizes: dict[str, int] = {key: 0 for key in latencies}
                initial = []
                active = []
                for token in tokens:
                    start = time.perf_counter()
                    response = await client.get(
                        "/api/v1/runtime",
                        headers={"Cookie": "freight_session=" + token},
                    )
                    response.raise_for_status()
                    initial.append((time.perf_counter() - start) * 1000)
                    active.append(len(response.json()["transports"]))
                # Warm only the runtime, never preload a world route catalogue.
                for index in range(100):
                    for token in tokens:
                        for resource in latencies:
                            start = time.perf_counter()
                            response = await client.get(
                                "/api/v1/" + resource,
                                headers={"Cookie": "freight_session=" + token},
                            )
                            elapsed = (time.perf_counter() - start) * 1000
                            response.raise_for_status()
                            latencies[resource].append(elapsed)
                            sizes[resource] = max(
                                sizes[resource], len(response.content)
                            )
                            if resource in {
                                "runtime",
                                "map/traffic?representation=summary",
                            }:
                                assert "route_geojson" not in response.text
                results = {
                    key: {
                        "requests": len(values),
                        "p95_ms": round(
                            sorted(values)[int(len(values) * 0.95) - 1], 2
                        ),
                        "median_ms": round(statistics.median(values), 2),
                        "max_ms": round(max(values), 2),
                        "max_json_bytes": sizes[key],
                    }
                    for key, values in latencies.items()
                }
                with database.connect() as connection:
                    templates_after = connection.execute(
                        "SELECT COUNT(*) FROM market_templates"
                    ).fetchone()[0]
                report = {
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "logical_cpus": os.cpu_count(),
                    "players": len(owners),
                    "vehicles": vehicles,
                    "templates_before": templates_before,
                    "templates_after": templates_after,
                    "active_transports": active,
                    "first_runtime_ms": initial,
                    "resources": results,
                    "browser": browser_report,
                    "provider": "deterministic isolated worker fixtures",
                    "source_unchanged": sha256(source.read_bytes()).hexdigest()
                    == original,
                }
                (output / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                assert report["source_unchanged"]
                assert templates_after > templates_before
                assert max(latencies["system/health"]) < 1000
                assert all(item["p95_ms"] <= 250 for item in results.values())
                assert (
                    sizes["runtime"]
                    + sizes["map/traffic?representation=summary"]
                    <= 250 * 1024
                )
                # Report the first process-cold load, including settlement,
                # for explicit acceptance; its 3.39 s was accepted by the
                # user. Subsequent player loads retain the two-second gate.
                assert all(
                    profile["playable_ms"] <= 2000
                    for profile in browser_report["profiles"][1:]
                )
                print(json.dumps(report, indent=2))
    finally:
        for child in reversed(children):
            await stop_child(child)


if __name__ == "__main__":
    asyncio.run(main())
