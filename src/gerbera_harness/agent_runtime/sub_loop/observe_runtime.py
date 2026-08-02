import json
from dataclasses import dataclass
from pathlib import Path

from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationStatusEnum,
    ObservationToolCallSchema,
    observation_adapter,
    observation_review_adapter,
)
from gerbera_harness.agent.model.mcp_client import MCPClient
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.main_loop.utils import append_message


PROMPT_DIRECTORY = Path(__file__).resolve().parents[2] / "prompts" / "sub"
OBSERVATION_REVIEW_PROMPT = (
    PROMPT_DIRECTORY / "OBSERVATION_REVIEW.md"
).read_text().strip()

# All we do here is feed context into messages
@dataclass
class ObservationRuntime:
    model: Model
    messages: list[dict[str, object]]
    mcp_url: str

    async def run_observation(
        self,
        system_prompt: str,
        hypothesis_prompt: str,
    ) -> ObservationStatusEnum:
        async with MCPClient(self.mcp_url) as mcp_client:
            client = self.model.get_agent_client()
            tools = await mcp_client.list_tools()
            allowed_tool_names = frozenset(tool.name for tool in tools)

            append_message(
                self.messages,
                role="user",
                content=hypothesis_prompt,
            )

            while True:
                raw_response = client.send(
                    self.messages,
                    system_prompt,
                    observation_adapter.json_schema(),
                )
                response = observation_adapter.validate_json(raw_response)
                observation = response.observation

                append_message(
                    self.messages,
                    role="assistant",
                    content=response.model_dump_json(),
                )

                if isinstance(observation, ObservationToolCallSchema):
                    result = await mcp_client.call_tool(
                        name=observation.tool_name,
                        arguments=observation.arguments,
                        allowed_tool_names=allowed_tool_names,
                    )
                    append_message(
                        self.messages,
                        role="user",
                        content=json.dumps(
                            {
                                "tool_name": observation.tool_name,
                                "result": result,
                            }
                        ),
                    )
                    continue

                review_response = client.send(
                    self.messages,
                    OBSERVATION_REVIEW_PROMPT,
                    observation_review_adapter.json_schema(),
                )

                review = observation_review_adapter.validate_json(
                    review_response
                )

                if review.status in {
                    ObservationStatusEnum.READY,
                    ObservationStatusEnum.BLOCKED,
                    ObservationStatusEnum.COMPLETE,
                }:
                    break

                append_message(
                    self.messages,
                    role="user",
                    content=json.dumps(
                        {"observation_review_feedback": review.feedback}
                    ),
                )

            return review.status
