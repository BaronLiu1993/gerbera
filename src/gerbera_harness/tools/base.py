from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    read_only: bool = False
    destructive: bool = False

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "read_only": self.read_only,
            "destructive": self.destructive,
        }


class LocalTool(Protocol):
    @property
    def spec(self) -> ToolSpec:
        raise NotImplementedError

    async def call(self, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError
