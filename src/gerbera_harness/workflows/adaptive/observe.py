import json
from dataclasses import dataclass
from datetime import datetime, timezone

from gerbera_harness.domain.adaptive import (
    ObservationResponseSchema,
    ObservationResultSchema,
    ObservationReviewSchema,
    ObservationStatusEnum,
    ObservationToolCallSchema,
    ObservationValueSchema,
    JsonScalar,
    observation_adapter,
    observation_review_adapter,
)
from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.infrastructure.llm import Model
from gerbera_harness.workflows.adaptive.context import (
    SubAgentPromptContextBuilder,
)
from gerbera_harness.memory import WorldStateSchema
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.tools.registry import LocalToolRegistry

OBSERVATION_PROMPT = load_prompt(PromptTypeEnum.SUB, "OBSERVE.md")
OBSERVATION_REVIEW_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "OBSERVATION_REVIEW.md",
)


# All we do here is feed context into messages
@dataclass
class ObservationRuntime:
    model: Model
    mcp_url: str
    context_builder: SubAgentPromptContextBuilder
    messages: list[dict[str, object]]
    observations: list[WorldStateSchema]
    tool_events: list[dict[str, object]]
    local_tool_registry: LocalToolRegistry

    async def run_observation(self) -> ObservationStatusEnum:
        response = await self.request_observation()

        if self.is_tool_call(response):
            return await self.run_tool_call(response)

        observation = self.observation_result(response)
        review = await self.review_observation()

        if self.is_terminal_review(review.status):
            self.record_observation_status(review.status)
            self.record_world_state(observation)
            return review.status

        self.record_observation_feedback(review.feedback)
        return ObservationStatusEnum.CONTINUE

    async def request_observation(self) -> ObservationResponseSchema:
        client = self.model.get_agent_client()
        raw_response = await client.send(
            self.context_builder.build(),
            OBSERVATION_PROMPT,
            ObservationResponseSchema.model_json_schema(),
        )
        response = observation_adapter.validate_json(raw_response)
        self.messages.append(
            {"role": "assistant", "content": response.model_dump_json()}
        )
        return response

    async def run_tool_call(
        self,
        response: ObservationResponseSchema,
    ) -> ObservationStatusEnum:
        observation = self.tool_call_observation(response)
        result = await self.call_observation_tool(observation)
        self.record_tool_result(observation, result)
        return ObservationStatusEnum.CONTINUE

    def tool_call_observation(
        self,
        response: ObservationResponseSchema,
    ) -> ObservationToolCallSchema:
        return ObservationToolCallSchema(
            content_type="tool_call",
            tool_name=self.require_tool_name(response.tool_name),
            arguments=self.values_to_dict(response.arguments),
        )

    async def call_observation_tool(
        self,
        observation: ObservationToolCallSchema,
    ) -> object:
        if self.local_tool_registry.has(observation.tool_name):
            return await self.local_tool_registry.call_tool(
                observation.tool_name,
                observation.arguments,
            )
        return await self.call_mcp_tool(observation)

    async def review_observation(self) -> ObservationReviewSchema:
        client = self.model.get_agent_client()
        review_response = await client.send(
            self.context_builder.build(),
            OBSERVATION_REVIEW_PROMPT,
            ObservationReviewSchema.model_json_schema(),
        )
        return observation_review_adapter.validate_json(review_response)

    @staticmethod
    def is_tool_call(response: ObservationResponseSchema) -> bool:
        return response.content_type == "tool_call"

    @staticmethod
    def is_terminal_review(status: ObservationStatusEnum) -> bool:
        return status in {
            ObservationStatusEnum.READY,
            ObservationStatusEnum.BLOCKED,
            ObservationStatusEnum.COMPLETE,
        }

    def record_observation_status(
        self,
        status: ObservationStatusEnum,
    ) -> None:
        self.messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {"observation_status": status.value}
                ),
            }
        )

    def record_observation_feedback(self, feedback: str) -> None:
        self.messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {"observation_review_feedback": feedback}
                ),
            }
        )

    def observation_result(
        self,
        response: ObservationResponseSchema,
    ) -> ObservationResultSchema:
        if response.reason is None:
            raise ValueError("Observation finish requires a reason")
        if response.summary is None:
            raise ValueError("Observation finish requires a summary")
        return ObservationResultSchema(
            content_type="finish",
            reason=response.reason,
            summary=response.summary,
            result=self.values_to_dict(response.result),
        )

    @staticmethod
    def values_to_dict(
        values: list[ObservationValueSchema],
    ) -> dict[str, JsonScalar]:
        return {value.key: value.value for value in values}

    @staticmethod
    def require_tool_name(tool_name: str | None) -> str:
        if tool_name is None:
            raise ValueError("Observation tool call requires a tool name")
        return tool_name

    async def call_mcp_tool(
        self,
        observation: ObservationToolCallSchema,
    ) -> object:
        async with MCPClient(self.mcp_url) as mcp_client:
            tools = await mcp_client.list_tools()
            allowed_tool_names = frozenset(tool.name for tool in tools)
            return await mcp_client.call_tool(
                name=observation.tool_name,
                arguments=observation.arguments,
                allowed_tool_names=allowed_tool_names,
            )

    def record_tool_result(
        self,
        observation: ObservationToolCallSchema,
        result: object,
    ) -> None:
        self.tool_events.append(
            {
                "tool_name": observation.tool_name,
                "arguments": observation.arguments,
                "status": "success",
                "result": result,
            }
        )
        self.messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "tool_name": observation.tool_name,
                        "result": result,
                    }
                ),
            }
        )

    def record_world_state(
        self,
        observation: ObservationResultSchema,
    ) -> None:
        self.observations.append(
            WorldStateSchema(
                observed_at=datetime.now(timezone.utc),
                state={
                    "summary": observation.summary,
                    **observation.result,
                },
            )
        )
