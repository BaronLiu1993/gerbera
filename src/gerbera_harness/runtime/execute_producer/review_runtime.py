import json
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import (
    EventSchema,
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
    WorldStateSchema,
)
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.runtime.context import ReviewContextBuilder
from gerbera_harness.runtime.execute_producer.schemas.review import (
    ExecuteProducerResult,
)

REVIEW_PROMPT = load_prompt(
    PromptTypeEnum.MAIN,
    "REVIEW.md",
)


@dataclass
class ReviewRuntime:
    model: Model
    memory: Memory
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]]
    context_builder: ReviewContextBuilder
    prev_state_context: str

    async def get_current_environment_state(self) -> dict[str, Any]:
        return await self.call_tool(
            "get_current_environment_state",
            {},
        )

    async def get_current_hardware_state(self) -> dict[str, Any]:
        return await self.call_tool(
            "get_current_hardware_state",
            {},
        )

    def update_memory(
        self,
        environment_state: dict[str, Any],
        hardware_state: dict[str, Any],
    ) -> None:
        task_id = self.memory.require_task_state().current_task_id
        previous_world_state = self.memory.world_state
        previous_hardware_state = (
            self.memory.physical_configuration.hardware_state_by_name
        )
        world_state = WorldStateSchema(
            session_id=self.memory.session_id,
            environment_state=environment_state,
        )

        if previous_world_state.environment_state != environment_state:
            self.memory.insert_event(
                EventSchema(
                    session_id=self.memory.session_id,
                    event_type=EventTypeEnum.WORLD_STATE_UPDATED,
                    source_type=SourceTypeEnum.MCP_TOOL,
                    source_name="get_current_environment_state",
                    payload={
                        "source_runtime": "review_runtime",
                        "state_kind": "environment",
                        "state": environment_state,
                    },
                    task_id=task_id,
                )
            )

        if previous_hardware_state != hardware_state:
            self.memory.insert_event(
                EventSchema(
                    session_id=self.memory.session_id,
                    event_type=EventTypeEnum.PHYSICAL_CONFIGURATION_UPDATED,
                    source_type=SourceTypeEnum.MCP_TOOL,
                    source_name="get_current_hardware_state",
                    payload={
                        "source_runtime": "review_runtime",
                        "state_kind": "hardware",
                        "state": hardware_state,
                    },
                    task_id=task_id,
                )
            )

        self.memory.define_world_state(world_state)
        self.memory.update_hardware_state_by_name(hardware_state)
        self.memory.rebuild_temporal_state()

    def update_memory_with_review(self, agent_payload: dict[str, Any]) -> None:
        task_id = self.memory.require_task_state().current_task_id
        review_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.REVIEW_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="review_runtime",
            payload=agent_payload,
            task_id=task_id,
        )
        self.memory.insert_event(review_event)
        self.memory.rebuild_temporal_state()

    async def run_review(self) -> ExecuteProducerResult:
        client = self.model.get_agent_client()

        environment_state = await self.get_current_environment_state()
        hardware_state = await self.get_current_hardware_state()
        self.update_memory(environment_state, hardware_state)

        review_context = self.context_builder.build_runtime_context()
        context = {
            "review_context": review_context,
            "prev_state_context": self.prev_state_context,
        }

        raw_response = await client.send(
            [
                {
                    "role": "user",
                    "content": json.dumps(context, indent=2),
                }
            ],
            REVIEW_PROMPT,
            ExecuteProducerResult.model_json_schema(),
        )

        review = ExecuteProducerResult.model_validate_json(raw_response)
        self.update_memory_with_review(review.model_dump(mode="json"))
        return review
