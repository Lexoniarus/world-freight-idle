"""Guard the final boundaries, including indirect and aliased imports."""

import ast
from importlib.util import resolve_name
from pathlib import Path


def imported_modules(source, module):
    tree = ast.parse(source)
    imports = set()
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                prefix = resolve_name(
                    "." * node.level + prefix, module.rsplit(".", 1)[0]
                )
            imports.add(prefix)
            for alias in node.names:
                target = prefix + "." + alias.name
                imports.add(target)
                aliases[alias.asname or alias.name] = target
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        head, separator, tail = name.partition(".")
        resolved = aliases.get(head, head) + separator + tail
        if resolved in {"importlib.import_module", "__import__"}:
            if node.args and isinstance(node.args[0], ast.Constant):
                target = node.args[0].value
                if isinstance(target, str):
                    if target.startswith(".") and len(node.args) > 1:
                        package = ast.literal_eval(node.args[1])
                        target = resolve_name(target, package)
                    imports.add(target)
    return imports


def forbidden_dependencies(module, sources, forbidden, visited=None):
    visited = set() if visited is None else visited
    if module in visited or module not in sources:
        return set()
    visited.add(module)
    violations = set()
    for imported in imported_modules(sources[module], module):
        if any(
            imported == p or imported.startswith(p + ".") for p in forbidden
        ):
            violations.add(imported)
        # The API calls the explicit composition root; do not flatten its DI.
        if imported != "app.bootstrap":
            candidate = imported
            while candidate and candidate not in sources:
                candidate = candidate.rpartition(".")[0]
            if candidate == "app.bootstrap":
                continue
            violations.update(
                forbidden_dependencies(candidate, sources, forbidden, visited)
            )
    return violations


def test_final_domain_and_service_boundaries_reject_indirect_imports():
    root = Path(__file__).resolve().parents[1]
    sources = {
        ".".join(path.relative_to(root).with_suffix("").parts): path.read_text(
            encoding="utf-8"
        )
        for path in (root / "app").rglob("*.py")
    }
    for module, source in sources.items():
        if not module.startswith(("app.domain.", "app.services.", "app.api.")):
            continue
        forbidden = ["sqlite3", "app.repositories", "httpx", "app.providers"]
        if not module.startswith("app.api."):
            forbidden.extend(("fastapi", "app.api", "app.bootstrap"))
        if module.startswith("app.domain."):
            forbidden.append("app.services")
        assert not forbidden_dependencies(module, sources, forbidden), module
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(
                node.func, ast.Attribute
            ):
                assert node.func.attr not in {
                    "execute",
                    "executemany",
                    "executescript",
                    "get_json",
                    "set_json",
                }, module
            if module.startswith("app.domain."):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in {
                        "to_dict",
                        "from_dict",
                        "to_json",
                        "from_json",
                    }, module
                if isinstance(node, ast.Call):
                    assert ast.unparse(node.func) not in {
                        "asdict",
                        "json.dumps",
                        "json.loads",
                    }, module
    for obsolete in ("app/repositories/sqlite_store.py", "app/seed_data.py"):
        assert not (root / obsolete).exists()


def test_boundary_checker_detects_reexports_relative_and_dynamic_imports():
    variants = (
        "from ..repositories import game_state",
        "from app.repositories.game_state import SqliteGameUnitOfWork as Uow",
        "import importlib as loader\nloader.import_module('app.repositories.game_state')",
        "from importlib import import_module as load\nload('.game_state', 'app.repositories')",
        "__import__('app.repositories.game_state')",
        "from app.shared import Repository",
    )
    for source in variants:
        sources = {
            "app.services.example": source,
            "app.shared": "from app.repositories.game_state import Repository",
        }
        assert forbidden_dependencies(
            "app.services.example", sources, ["app.repositories"]
        )
    sources = {
        "app.services.example": "from app.domain.state_ports import GameUnitOfWork",
        "app.domain.state_ports": "from typing import Protocol",
    }
    assert not forbidden_dependencies(
        "app.services.example", sources, ["app.repositories"]
    )
