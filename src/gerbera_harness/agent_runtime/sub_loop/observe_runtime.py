import json
from dataclasses import dataclass

from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationFinishSchema,
    ObservationStatusEnum,
    ObservationToolCallSchema,
    observation_adapter,
    observation_review_adapter,
)
from gerbera_harness.agent.model.mcp_client import MCPClient
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.context_builder import ContextBuilder
from gerbera_harness.memory import (
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
)
from gerbera_harness.prompts import PromptTypeEnum, load_prompt

OBSERVATION_PROMPT = load_prompt(PromptTypeEnum.SUB, "OBSERVE.md")
OBSERVATION_REVIEW_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "OBSERVATION_REVIEW.md",
)


# All we do here is feed context into messages
@dataclass
class ObservationRuntime:
    model: Model
    memory: Memory
    mcp_url: str
    context_builder: ContextBuilder

    async def run_observation(self) -> ObservationStatusEnum:
        async with MCPClient(self.mcp_url) as mcp_client:
            client = self.model.get_agent_client()
            tools = await mcp_client.list_tools()
            allowed_tool_names = frozenset(
                tool.name
                for tool in tools
                if tool.annotations is not None
                and tool.annotations.readOnlyHint is True
            )

            raw_response = client.send(
                self.context_builder.build(),
                OBSERVATION_PROMPT,
                observation_adapter.json_schema(),
            )
            response = observation_adapter.validate_json(raw_response)
            observation = response.observation

            self.memory.append_message(
                "assistant",
                response.model_dump_json(),
            )

            if isinstance(observation, ObservationToolCallSchema):
                result = await mcp_client.call_tool(
                    name=observation.tool_name,
                    arguments=observation.arguments,
                    allowed_tool_names=allowed_tool_names,
                )
                self._record_tool_result(observation, result)
                return ObservationStatusEnum.CONTINUE

            review_response = client.send(
                self.context_builder.build(),
                OBSERVATION_REVIEW_PROMPT,
                observation_review_adapter.json_schema(),
            )

            review = observation_review_adapter.validate_json(review_response)

            if review.status in {
                ObservationStatusEnum.READY,
                ObservationStatusEnum.BLOCKED,
                ObservationStatusEnum.COMPLETE,
            }:
                self.memory.append_message(
                    "user",
                    json.dumps({"observation_status": review.status}),
                )
                self._record_world_state(observation, review.status)
                return review.status

            self.memory.append_message(
                "user",
                json.dumps({"observation_review_feedback": review.feedback}),
            )

            return ObservationStatusEnum.CONTINUE

    def _record_tool_result(
        self,
        observation: ObservationToolCallSchema,
        result: object,
    ) -> None:
        self.memory.append_event(
            event_type=EventTypeEnum.TOOL_CALL,
            source_type=SourceTypeEnum.MCP_TOOL,
            payload={
                "tool_name": observation.tool_name,
                "arguments": observation.arguments,
                "status": "success",
                "result": result,
            },
        )
        self.memory.append_message(
            "user",
            json.dumps(
                {
                    "tool_name": observation.tool_name,
                    "result": result,
                }
            ),
        )

    def _record_world_state(
        self,
        observation: ObservationFinishSchema,
        status: ObservationStatusEnum,
    ) -> None:
        world_state = self.memory.append_world_state(observation.world_state)
        self.memory.append_event(
            event_type=EventTypeEnum.WORLD_STATE_UPDATED,
            source_type=SourceTypeEnum.MODEL,
            payload={
                "review_status": status.value,
                "world_state": world_state.model_dump(mode="json"),
            },
        )
