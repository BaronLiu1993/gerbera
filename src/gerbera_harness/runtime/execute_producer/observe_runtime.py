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
    ObservationResult,
    observation_result_adapter,
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
        world_state = WorldStateSchema(
            session_id=self.memory.session_id,
            environment_state=environment_state,
            hardware_state=hardware_state,
            sources=[
                "observe_runtime:get_current_environment_state",
                "observe_runtime:get_current_hardware_state",
            ],
        )

        if previous_world_state.environment_state != environment_state:
            self.memory.insert_event(
                EventSchema(
                    session_id=self.memory.session_id,
                    event_type=EventTypeEnum.WORLD_STATE_UPDATED,
                    source_type=SourceTypeEnum.MCP_TOOL,
                    source_name="get_current_environment_state",
                    payload={
                        "source_runtime": "observe_runtime",
                        "state_kind": "environment",
                        "state": environment_state,
                    },
                    task_id=task_id,
                )
            )

        if previous_world_state.hardware_state != hardware_state:
            self.memory.insert_event(
                EventSchema(
                    session_id=self.memory.session_id,
                    event_type=EventTypeEnum.WORLD_STATE_UPDATED,
                    source_type=SourceTypeEnum.MCP_TOOL,
                    source_name="get_current_hardware_state",
                    payload={
                        "source_runtime": "observe_runtime",
                        "state_kind": "hardware",
                        "state": hardware_state,
                    },
                    task_id=task_id,
                )
            )

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

        raw_response = await client.send(
            [
                {
                    "role": "user",
                    "content": json.dumps(context, indent=2),
                }
            ],
            OBSERVATION_PROMPT,
            observation_result_adapter.json_schema(),
        )

        result = observation_result_adapter.validate_json(raw_response)
        self.update_memory_with_plan(result.model_dump(mode="json"))

        environment_state = await self.get_current_environment_state()
        hardware_state = await self.get_current_hardware_state()
        self.update_memory(environment_state, hardware_state)

        return result
