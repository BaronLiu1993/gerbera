import json
from dataclasses import dataclass
from datetime import datetime, timezone

from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationFinishSchema,
    ObservationStatusEnum,
    ObservationToolCallSchema,
    observation_adapter,
    observation_review_adapter,
)
from gerbera_harness.agent.model.mcp_client import MCPClient
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.subagent_context import (
    SubAgentPromptContextBuilder,
)
from gerbera_harness.memory import WorldStateSchema
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_sdk.contracts.tool_contract import (
    ToolStage,
    tool_is_available_during,
)

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

    async def run_observation(self) -> ObservationStatusEnum:
        async with MCPClient(self.mcp_url) as mcp_client:
            client = self.model.get_agent_client()
            tools = await mcp_client.list_tools()
            allowed_tool_names = frozenset(
                tool.name
                for tool in tools
                if tool_is_available_during(tool, ToolStage.OBSERVATION)
            )

            raw_response = await client.send(
                self.context_builder.build(),
                OBSERVATION_PROMPT,
                observation_adapter.json_schema(),
            )
            response = observation_adapter.validate_json(raw_response)
            observation = response.observation

            self.messages.append(
                {"role": "assistant", "content": response.model_dump_json()}
            )

            if isinstance(observation, ObservationToolCallSchema):
                result = await mcp_client.call_tool(
                    name=observation.tool_name,
                    arguments=observation.arguments,
                    allowed_tool_names=allowed_tool_names,
                )
                self._record_tool_result(observation, result)
                return ObservationStatusEnum.CONTINUE

            review_response = await client.send(
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
                self.messages.append(
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"observation_status": review.status.value}
                        ),
                    }
                )
                self._record_world_state(observation)
                return review.status

            self.messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {"observation_review_feedback": review.feedback}
                    ),
                }
            )

            return ObservationStatusEnum.CONTINUE

    def _record_tool_result(
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

    def _record_world_state(
        self,
        observation: ObservationFinishSchema,
    ) -> None:
        self.observations.append(
            WorldStateSchema(
                observed_at=datetime.now(timezone.utc),
                state=observation.world_state,
            )
        )
