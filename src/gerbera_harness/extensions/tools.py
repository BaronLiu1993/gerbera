from dataclasses import dataclass

from gerbera_harness.infrastructure.database import DatabaseGateway
from gerbera_harness.infrastructure.sandbox import SandboxGateway
from gerbera_harness.runtime.extensions import HarnessRegistry
from gerbera_harness.tools.database import GetTableSchemasTool, QueryDatabaseTool
from gerbera_harness.tools.registry import LocalToolRegistry
from gerbera_harness.tools.sandbox import RunSandboxTool
from gerbera_harness.tools.sources import LocalToolSource


@dataclass(frozen=True)
class DatabaseToolsExtension:
    database: DatabaseGateway

    def register(self, registry: HarnessRegistry) -> None:
        tools = LocalToolRegistry()
        tools.register(GetTableSchemasTool(self.database))
        tools.register(QueryDatabaseTool(self.database))
        registry.register_tool_source(LocalToolSource(tools))


@dataclass(frozen=True)
class SandboxExtension:
    sandbox: SandboxGateway

    def register(self, registry: HarnessRegistry) -> None:
        tools = LocalToolRegistry()
        tools.register(RunSandboxTool(self.sandbox))
        registry.register_tool_source(LocalToolSource(tools))
