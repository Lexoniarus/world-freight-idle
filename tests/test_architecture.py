"""Keep application boundaries enforceable independently of style checks."""

import ast
from pathlib import Path

import httpx
import pytest

from app.domain.errors import GeocodingError, RoutingError
from app.providers.geocoding import NominatimGeocoder
from app.providers.routing import ValhallaTruckRouter


def test_domain_and_services_do_not_depend_on_transport_adapters():
    root = Path(__file__).resolve().parents[1] / "app"
    for folder in ("domain", "services", "api"):
        for path in (root / folder).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            modules = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    modules.append(node.module or "")
                elif isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
            forbidden = ("app.providers", "httpx")
            if folder == "domain":
                forbidden += ("app.services", "app.repositories", "fastapi")
            assert not any(
                module == prefix or module.startswith(prefix + ".")
                for module in modules
                for prefix in forbidden
            ), path


def test_api_does_not_construct_concrete_services():
    root = Path(__file__).resolve().parents[1] / "app" / "api"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert (
                    not node.func.id.endswith(
                        (
                            "Service",
                            "Repository",
                            "Store",
                            "Geocoder",
                            "Router",
                        )
                    )
                    or node.func.id == "APIRouter"
                ), path


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["network", "malformed"])
async def test_provider_failures_are_normalized_at_ports(store, failure):
    async def handler(request):
        if failure == "network":
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, text="not json")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        geocoder = NominatimGeocoder(
            store, client, "https://n.test", "test", 0
        )
        router = ValhallaTruckRouter(store, client, "https://r.test", "test")
        with pytest.raises(GeocodingError) as geocoding:
            await geocoder.geocode("uncached")
        with pytest.raises(RoutingError) as routing:
            await router.route(1, 2, 3, 4)
    assert geocoding.value.__cause__ is not None
    assert routing.value.__cause__ is not None
    assert store.get_geocode("uncached") is None


def test_profile_maintenance_keeps_cli_and_sql_out_of_service():
    root = Path(__file__).resolve().parents[1]
    rules = {
        "app/services/profile_maintenance.py": {
            "sqlite3",
            "argparse",
            "sys",
            "app.bootstrap",
        },
        "scripts/update_test_profile.py": {
            "sqlite3",
            "app.services.profile_maintenance",
            "app.repositories.sqlite_store",
            "app.repositories.accounts",
        },
    }
    for name, forbidden in rules.items():
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden, name
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name in forbidden for alias in node.names
                ), name
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in {
                        "SqliteStore",
                        "AccountRepository",
                        "SqliteVehicleCatalogue",
                    }, name
                if isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in {
                        "execute",
                        "executemany",
                        "executescript",
                    }, name
