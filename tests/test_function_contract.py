from __future__ import annotations

import ast
from pathlib import Path

from tests.function_test_manifest import FUNCTION_TESTS


def collect_concrete_callables(app_root: Path) -> set[str]:
    """Collect named implementations, including constructors and closures."""
    callables: set[str] = set()
    for path in app_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = "app." + ".".join(
            path.relative_to(app_root).with_suffix("").parts
        )
        protocol_names = {"typing.Protocol", "typing_extensions.Protocol"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in {
                "typing",
                "typing_extensions",
            }:
                protocol_names.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "Protocol"
                )
            if isinstance(node, ast.Import):
                protocol_names.update(
                    (alias.asname or alias.name) + ".Protocol"
                    for alias in node.names
                    if alias.name in {"typing", "typing_extensions"}
                )

        def visit(node: ast.AST, prefix: str, protocol: bool = False) -> None:
            if isinstance(node, ast.ClassDef):
                protocol = any(
                    ast.unparse(base).split("[")[0] in protocol_names
                    for base in node.bases
                )
                prefix += "." + node.name
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix += "." + node.name
                declarations = [
                    item
                    for item in node.body
                    if not (
                        isinstance(item, ast.Expr)
                        and isinstance(item.value, ast.Constant)
                        and isinstance(item.value.value, str)
                    )
                ]
                is_stub = all(
                    isinstance(item, ast.Pass)
                    or (
                        isinstance(item, ast.Expr)
                        and isinstance(item.value, ast.Constant)
                        and item.value.value is Ellipsis
                    )
                    for item in declarations
                )
                if not (protocol and is_stub):
                    callables.add(prefix)
                protocol = False
            for child in ast.iter_child_nodes(node):
                visit(child, prefix, protocol)

        visit(tree, module)
    return callables


def collect_test_functions(tests_root: Path) -> set[str]:
    names = set()
    for path in tests_root.glob("test_*.py"):
        tree = ast.parse(path.read_text())
        names.update(
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    return names


def test_every_python_core_callable_has_an_explicit_counter_test():
    root = Path(__file__).resolve().parents[1]
    concrete = collect_concrete_callables(root / "app")
    assert concrete == set(FUNCTION_TESTS), (
        "Function-test manifest drift. Missing or stale entries: "
        f"{sorted(concrete.symmetric_difference(FUNCTION_TESTS))}"
    )
    available_tests = collect_test_functions(root / "tests")
    missing_tests = {
        callable_name: test_name
        for callable_name, test_name in FUNCTION_TESTS.items()
        if test_name not in available_tests
    }
    assert not missing_tests, (
        f"Manifest points to missing tests: {missing_tests}"
    )


def test_callable_scanner_includes_constructors_and_nested_implementations(
    tmp_path,
):
    path = tmp_path / "example.py"
    path.write_text(
        """
from typing import Protocol as Port
class Dependency(Port):
    def operation(self): ...
    def concrete(self): return 2
class Service:
    def __init__(self): self.value = 1
    def operation(self):
        def nested(): return self.value
        return nested()
""",
        encoding="utf-8",
    )
    assert collect_concrete_callables(tmp_path) == {
        "app.example.Dependency.concrete",
        "app.example.Service.__init__",
        "app.example.Service.operation",
        "app.example.Service.operation.nested",
    }
