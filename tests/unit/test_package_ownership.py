import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def imports(paths) -> set[str]:
    modules = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


@pytest.mark.parametrize("package, forbidden", [
    ("gerbera_cli", {"gerbera_sdk", "gerbera_harness", "psycopg"}),
    ("gerbera_harness", {"gerbera_sdk", "gerbera_cli"}),
    ("gerbera_sdk", {"gerbera_harness", "gerbera_cli"}),
    ("gerbera_protocol", {"gerbera_sdk", "gerbera_harness", "gerbera_cli"}),
])
def test_packages_import_only_the_dependencies_they_own(package, forbidden) -> None:
    modules = imports((ROOT / "src" / package).rglob("*.py"))

    assert {module.split(".")[0] for module in modules}.isdisjoint(forbidden)


def test_legacy_harness_namespace_is_not_imported() -> None:
    paths = [*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py"), *ROOT.glob("*.py")]

    assert all(
        module != "gerbera_sdk.harness" and not module.startswith("gerbera_sdk.harness.")
        for module in imports(paths)
    )
