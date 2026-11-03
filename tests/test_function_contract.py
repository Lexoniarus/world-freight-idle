from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.function_test_manifest import FUNCTION_TESTS

TestFunction = ast.FunctionDef | ast.AsyncFunctionDef


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


def collect_test_functions(
    tests_root: Path,
) -> dict[str, tuple[Path, TestFunction]]:
    """Index uniquely named top-level tests with their owning modules."""
    functions: dict[str, tuple[Path, TestFunction]] = {}
    for path in tests_root.glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if node.name in functions:
                first_path = functions[node.name][0]
                raise AssertionError(
                    f"Duplicate test name {node.name}: {first_path}, {path}"
                )
            functions[node.name] = (path, node)
    return functions


def collect_manifest_declarations(path: Path) -> dict[str, list[int]]:
    """Index declarations before dictionary updates can overwrite them."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    declarations: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        keys: list[ast.expr | None] = []
        if isinstance(node, ast.Dict):
            keys = node.keys
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "FUNCTION_TESTS"
        ):
            keys = [node.targets[0].slice]
        for key in keys:
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value.startswith("app.")
            ):
                declarations.setdefault(key.value, []).append(key.lineno)
    return declarations


def has_direct_test_assertion(test: TestFunction) -> bool:
    """Return whether a test contains an assertion or expected rejection."""
    for node in ast.walk(test):
        if isinstance(node, ast.Assert):
            return True
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            expression = item.context_expr
            if not isinstance(expression, ast.Call):
                continue
            if isinstance(expression.func, ast.Attribute):
                if expression.func.attr == "raises":
                    return True
    return False


def test_every_python_core_callable_has_a_unique_asserting_test_reference():
    """Check the structural index; semantic relevance still needs review."""
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
    implicit_tests = {
        test_name
        for test_name in FUNCTION_TESTS.values()
        if not has_direct_test_assertion(available_tests[test_name][1])
    }
    assert not implicit_tests, (
        "Manifest tests need a direct assertion or expected rejection: "
        f"{sorted(implicit_tests)}"
    )


def test_manifest_test_names_are_unique_and_owner_modules_are_scoped(
    tmp_path,
):
    first = tmp_path / "test_first.py"
    second = tmp_path / "test_second.py"
    first.write_text("def test_contract(): assert True\n", encoding="utf-8")
    second.write_text("def test_contract(): assert False\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="Duplicate test name"):
        collect_test_functions(tmp_path)

    root = Path(__file__).resolve().parents[1]
    retired_collectors = {
        "test_market.py",
        "test_multiplayer.py",
        "test_review_regressions.py",
        "test_runtime_views.py",
        "test_stock_preparation.py",
    }
    present = {path.name for path in (root / "tests").glob("test_*.py")}
    assert retired_collectors.isdisjoint(present)


def test_manifest_declares_each_callable_once():
    path = Path(__file__).with_name("function_test_manifest.py")
    declarations = collect_manifest_declarations(path)
    duplicates = {
        name: lines for name, lines in declarations.items() if len(lines) > 1
    }

    assert not duplicates, f"Duplicate callable declarations: {duplicates}"
    assert set(declarations) == set(FUNCTION_TESTS)


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
