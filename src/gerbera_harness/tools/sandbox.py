from dataclasses import dataclass
from typing import Any

from gerbera_harness.gateway.sandbox_gateway import SandboxGateway
from gerbera_harness.tools.base import ToolSpec


@dataclass
class RunSandboxTool:
    session_id: str
    sandbox: SandboxGateway

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="run_sandbox",
            description="Run Python code inside the Gerbera sandbox.",
            input_schema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to run in the sandbox.",
                    }
                },
                "required": ["code"],
            },
            read_only=False,
            destructive=False,
        )

    async def call(self, arguments: dict[str, Any]) -> object:
        return self.sandbox.run_sandbox(
            session_id=self.session_id,
            code=arguments["code"],
        ).result
