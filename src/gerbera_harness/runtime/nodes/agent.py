from dataclasses import dataclass
import json

from pydantic import Field

from gerbera_harness.runtime.contracts import NodeContext
from gerbera_harness.runtime.nodes.prompt import PromptConfig, PromptNode
from gerbera_harness.runtime.state_machine.schemas import (
    NodeResult, WorkflowSchema, WorkflowState,
)


class AgentConfig(WorkflowSchema):
    prompt: str = Field(
        default="Use the available tools to answer the user's request.",
        min_length=1,
    )
    access: str = Field(default="all", pattern="^(all|read_only)$")


AGENT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "outcome": {"type": "string", "enum": ["tool_calls", "complete"]},
        "message": {"type": "string"},
        "calls": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "arguments_json": {"type": "string"},
                },
                "required": ["name", "arguments_json"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["outcome", "message", "calls"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class AgentNode:
    config: AgentConfig

    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult:
        tools = await context.services.tools.list_tools()
        if self.config.access == "read_only":
            tools = [tool for tool in tools if tool.read_only]
        history = list(context.input.get("history", []))
        input_data = {
            **context.input,
            "tools": [tool.model_dump() for tool in tools],
        }
        prompt_context = NodeContext(
            services=context.services, emit=context.emit,
            input=input_data, extra=context.extra,
        )
        prompt = PromptConfig(
            prompt=self.config.prompt + (
                "\nReturn tool_calls to request tools or complete for a final answer. "
                "Encode each call's arguments as a JSON object in arguments_json. "
                "Use only the listed tools. Do not claim execution without tool results."
            ),
            response_schema=AGENT_RESPONSE_SCHEMA,
            outcome_pointer="/outcome",
        )
        result = await PromptNode(prompt).execute(state, prompt_context)
        output = dict(result.output)
        calls = [
            {"name": call["name"], "arguments": json.loads(call["arguments_json"])}
            for call in output.pop("calls")
        ]
        allowed = {tool.name for tool in tools}
        if any(call["name"] not in allowed for call in calls):
            raise ValueError("Agent requested an unavailable tool")
        if result.outcome == "tool_calls" and not calls:
            raise ValueError("tool_calls requires at least one call")
        if result.outcome == "complete" and calls:
            raise ValueError("complete cannot include unexecuted calls")
        history.append({
            "message": output["message"], "calls": calls,
            "previous_results": context.input.get("results", []),
        })
        return NodeResult(outcome=result.outcome, output={
            **output, "calls": calls, "history": history,
        })
