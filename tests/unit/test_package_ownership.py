import ast
from pathlib import Path

import pytest


def imports(package: str) -> set[str]:
    modules = set()
    for path in (Path("src") / package).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize("package, forbidden", [
    ("gerbera_cli", {"gerbera_sdk", "gerbera_harness", "psycopg", "pydantic"}),
    ("gerbera_harness", {"gerbera_sdk", "gerbera_cli"}),
    ("gerbera_sdk", {"gerbera_harness", "gerbera_cli"}),
    ("gerbera_protocol", {"gerbera_sdk", "gerbera_harness", "gerbera_cli"}),
])
def test_packages_import_only_the_dependencies_they_own(package, forbidden) -> None:
    assert imports(package).isdisjoint(forbidden)
