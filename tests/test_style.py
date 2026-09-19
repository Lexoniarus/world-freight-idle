from pathlib import Path


def test_python_source_has_no_tabs_or_trailing_whitespace():
    root = Path(__file__).resolve().parents[1] / "app"
    for path in root.rglob("*.py"):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            assert "\t" not in line, f"Tab in {path}:{number}"
            assert line == line.rstrip(), (
                f"Trailing whitespace in {path}:{number}"
            )


def test_python_source_line_length_is_pep8_reasonable():
    root = Path(__file__).resolve().parents[1] / "app"
    violations = []
    for path in root.rglob("*.py"):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if len(line) > 79:
                violations.append(
                    f"{path.relative_to(root.parent)}:{number}:{len(line)}"
                )
    assert not violations, "Long lines:\n" + "\n".join(violations)
