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
from gerbera_harness.runtime.context import ObservationContextBuilder
from gerbera_harness.runtime.execute_producer.schemas.observe import (
    ObservationAction,
    ObservationDecision,
    ObservationResult,
)

OBSERVATION_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "OBSERVE.md",
)


@dataclass
class ObservationRuntime:
    model: Model
    memory: Memory
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]]
    context_builder: ObservationContextBuilder
    prev_state_context: str  # what do we want to gain from observing
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

    def update_memory_with_plan(self, agent_payload: dict[str, Any]) -> None:
        task_id = self.memory.require_task_state().current_task_id
        observe_plan_upload = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.OBSERVATION_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="observe_runtime",
            payload=agent_payload,
            task_id=task_id,
        )
        self.memory.insert_event(observe_plan_upload)

    async def run_observation(self) -> ObservationResult:
        client = self.model.get_agent_client()
        before_context = self.context_builder.build_runtime_context()
        context = {
            "observation_context": before_context,
            "prev_state_context": self.prev_state_context,
        }

        for _ in range(self.max_attempts):
            raw_response = await client.send(
                [
                    {
                        "role": "user",
                        "content": json.dumps(context, indent=2),
                    }
                ],
                OBSERVATION_PROMPT,
                ObservationAction.model_json_schema(),
            )

            action = ObservationAction.model_validate_json(raw_response)
            # do not evaluate yet just make it opened looped system for complexity reduction
            self.update_memory_with_plan(action.model_dump(mode="json"))

            # update the world state
            environment_state = await self.get_current_environment_state()
            hardware_state = await self.get_current_hardware_state()
            self.update_memory(environment_state, hardware_state)

            # for now lets just say it is always accepted, no error handling for now
            return ObservationResult(
                context=action.context,
                actions=action.actions,
                result=ObservationDecision.SUCCESS,
            )

        # only code happy path for now
        return ObservationResult(
            context="FAILED TASK",
            actions=[],
            result=ObservationDecision.FAIL,
        )
