import asyncio

import pytest

from gerbera_harness.gateway.sandbox_gateway import SandboxResult
from gerbera_harness.tools.database import QueryDatabaseTool
from gerbera_harness.tools.registry import LocalToolRegistry
from gerbera_harness.tools.sandbox import RunSandboxTool


class FakeDatabaseGateway:
    queries: list[str]

    def __init__(self) -> None:
        self.queries = []

    async def execute_query(self, query: str) -> list[dict]:
        self.queries.append(query)
        return [{"value": 1}]


class FakeSandboxGateway:
    calls: list[tuple[str, str]]

    def __init__(self) -> None:
        self.calls = []

    def run_sandbox(self, session_id: str, code: str) -> SandboxResult:
        self.calls.append((session_id, code))
        return SandboxResult(
            session_id=session_id,
            run_id="run-1",
            result={"ok": True},
        )


def test_local_tool_registry_routes_registered_tool() -> None:
    database = FakeDatabaseGateway()
    registry = LocalToolRegistry()
    registry.register(QueryDatabaseTool(database))

    result = asyncio.run(
        registry.call_tool(
            "query_database",
            {"query": "delete from events"},
        )
    )

    assert result == [{"value": 1}]
    assert database.queries == ["delete from events"]


def test_local_tool_registry_rejects_missing_tool() -> None:
    registry = LocalToolRegistry()

    with pytest.raises(ValueError, match="not registered"):
        asyncio.run(registry.call_tool("missing", {}))


def test_run_sandbox_tool_delegates_to_gateway() -> None:
    sandbox = FakeSandboxGateway()
    tool = RunSandboxTool(session_id="session-1", sandbox=sandbox)

    result = asyncio.run(
        tool.call({"code": "print({'ok': True})"})
    )

    assert result == {"ok": True}
    assert sandbox.calls == [("session-1", "print({'ok': True})")]
