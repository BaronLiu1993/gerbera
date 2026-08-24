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
    ReviewAction,
    ReviewResult,
)
from gerbera_harness.runtime.execute_producer.state_machine import LoopDecision

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
    prev_state_context: (
        str  # what do we want to gain from observing that checks if it was done
    )
    max_attempts: int = 3

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
        world_state = WorldStateSchema(
            session_id=self.memory.session_id,
            environment_state=environment_state,
            hardware_state=hardware_state,
            sources=[],
        )
        environment_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.WORLD_STATE_UPDATED,
            source_type=SourceTypeEnum.MCP_TOOL,
            source_name="get_current_environment_state",
            payload=environment_state,
            task_id=task_id,
        )
        hardware_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.WORLD_STATE_UPDATED,
            source_type=SourceTypeEnum.MCP_TOOL,
            source_name="get_current_hardware_state",
            payload=hardware_state,
            task_id=task_id,
        )

        self.memory.insert_event(environment_event)
        self.memory.insert_event(hardware_event)
        self.memory.define_world_state(world_state)
        self.memory.rebuild_temporal_state()

    def update_memory_with_review(self, agent_payload: dict[str, Any]) -> None:
        task_id = self.memory.require_task_state().current_task_id
        review_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.OBSERVATION_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="review_runtime",
            payload=agent_payload,
            task_id=task_id,
        )
        self.memory.insert_event(review_event)

    async def run_review(self) -> ReviewResult:
        client = self.model.get_agent_client()
        before_context = self.context_builder.build_runtime_context()
        context = {
            "review_context": before_context,
            "prev_state_context": self.prev_state_context,
        }

        for _ in range(self.max_attempts):
            raw_response = await client.send(
                context,
                REVIEW_PROMPT,
                ReviewAction.model_json_schema(),
            )

            action = ReviewAction.model_validate_json(raw_response)
            self.update_memory_with_review(action.model_dump(mode="json"))

            environment_state = await self.get_current_environment_state()
            hardware_state = await self.get_current_hardware_state()
            self.update_memory(environment_state, hardware_state)

            return ReviewResult(
                context=action.context,
                actions=action.actions,
                result=LoopDecision.SUCCESS,
            )

        return ReviewResult(
            context="FAILED TASK",
            actions=[],
            result=LoopDecision.FAIL,
        )
