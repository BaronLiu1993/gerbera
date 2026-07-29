from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ALLOWED_SDK_IMPORTS_FOR_HARNESS = (
    "gerbera_sdk.events.event_key",
    "gerbera_sdk.events.rules",
)
IMPORT_PATTERN = re.compile(
    r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_.]*)",
    re.MULTILINE,
)


def _file_imports(path: Path) -> list[tuple[Path, str]]:
    return [
        (path, match.group(1))
        for match in IMPORT_PATTERN.finditer(path.read_text())
    ]


def _python_imports(package_path: Path) -> list[tuple[Path, str]]:
    imports: list[tuple[Path, str]] = []
    for path in package_path.rglob("*.py"):
        imports.extend(_file_imports(path))
    return imports


def test_sdk_does_not_depend_on_harness() -> None:
    violations = [
        (path, module)
        for path, module in _python_imports(SRC / "gerbera_sdk")
        if module == "gerbera_harness"
        or module.startswith("gerbera_harness.")
    ]

    assert violations == []


def test_harness_uses_only_declared_sdk_interfaces() -> None:
    violations = [
        (path, module)
        for path, module in _python_imports(SRC / "gerbera_harness")
        if module == "gerbera_sdk"
        or (
            module.startswith("gerbera_sdk.")
            and not any(
                module == allowed or module.startswith(f"{allowed}.")
                for allowed in ALLOWED_SDK_IMPORTS_FOR_HARNESS
            )
        )
    ]

    assert violations == []


def test_legacy_harness_namespace_is_not_imported() -> None:
    imports = _python_imports(SRC) + _python_imports(ROOT / "tests")
    for path in ROOT.glob("*.py"):
        imports.extend(_file_imports(path))

    violations = [
        (path, module)
        for path, module in imports
        if module == "gerbera_sdk.harness"
        or module.startswith("gerbera_sdk.harness.")
    ]

    assert violations == []
