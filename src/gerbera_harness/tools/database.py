from dataclasses import dataclass
from typing import Any

from gerbera_harness.gateway.database_gateway import DatabaseGateway
from gerbera_harness.tools.base import ToolSpec


@dataclass
class QueryDatabaseTool:
    database: DatabaseGateway

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="query_database",
            description="Execute a read-only SQL query against the Gerbera database.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute.",
                    }
                },
                "required": ["query"],
            },
            read_only=True,
            destructive=False,
        )

    async def call(self, arguments: dict[str, Any]) -> list[dict]:
        return await self.database.execute_query(arguments["query"])
