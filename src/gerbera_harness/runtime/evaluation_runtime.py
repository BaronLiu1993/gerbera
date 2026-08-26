import json
from dataclasses import dataclass

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.runtime.context import EvaluateContextBuilder
from gerbera_harness.runtime.schemas import EvaluationResultSchema
from gerbera_harness.tools.client import ToolClient


EVALUATION_PROMPT = load_prompt(PromptTypeEnum.MAIN, "EVALUATION.md")


@dataclass
class EvaluationRuntime:
    model: Model
    memory: Memory
    tool_client: ToolClient

    async def run_evaluation(self) -> EvaluationResultSchema:
        client = self.model.get_agent_client()
        available_tools = [
            tool.model_dump()
            for tool in await self.tool_client.list_tools()
        ]
        read_only_tools = [
            tool
            for tool in available_tools
            if tool.get("read_only") is True
        ]
        context_builder = EvaluateContextBuilder(
            memory=self.memory,
            available_tools=read_only_tools,
        )
        context = {
            "evaluation_context": context_builder.build_runtime_context(),
        }

        raw_response = await client.send(
            [
                {
                    "role": "user",
                    "content": json.dumps(context, indent=2),
                }
            ],
            EVALUATION_PROMPT,
            EvaluationResultSchema.model_json_schema(),
        )

        return EvaluationResultSchema.model_validate_json(raw_response)
