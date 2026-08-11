from dataclasses import dataclass
from typing import Any

from gerbera_harness.gateway.sandbox_gateway import SandboxGateway
from gerbera_harness.tools.base import ToolSpec


@dataclass
class RunSandboxTool:
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
        sandbox_result = self.sandbox.run_sandbox(code=arguments["code"])
        return {
            "run_id": sandbox_result.run_id,
            "result": sandbox_result.result,
        }
