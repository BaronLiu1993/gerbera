import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
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
from gerbera_harness.runtime.context import (
    ObservationContextBuilder,
    ObservationReviewContextBuilder,
)
from gerbera_harness.runtime.execute_producer.schemas.observe import (
    ObservationIterationContext,
    ObservationIterationRole,
    ObservationReviewResult,
    ObservationResult,
    observation_review_result_adapter,
    observation_result_adapter,
)

OBSERVATION_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "OBSERVE.md",
)

OBSERVATION_REVIEW_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "OBSERVE_REVIEW.md",
)


@dataclass
class ObservationRuntime:
    model: Model
    memory: Memory
    call_tool: Callable[[str, dict[str, Any]], Awaitable[Any]]
    context_builder: ObservationContextBuilder
    review_context_builder: ObservationReviewContextBuilder
    prev_state_context: str
    max_iterations: int
    prev_iteration_context: list[ObservationIterationContext] = field(
        default_factory=list
    )
    current_iteration: int = 1

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
                        "source_runtime": "observe_runtime",
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
                        "source_runtime": "observe_runtime",
                        "state_kind": "hardware",
                        "state": hardware_state,
                    },
                    task_id=task_id,
                )
            )

        self.memory.define_world_state(world_state)
        self.memory.update_hardware_state_by_name(hardware_state)
        self.memory.rebuild_temporal_state()

    def append_iteration_context(
        self,
        role: ObservationIterationRole,
        content: dict[str, Any],
    ) -> ObservationIterationContext:
        iteration_context = ObservationIterationContext(
            iteration=self.current_iteration,
            role=role,
            content=content,
        )
        self.prev_iteration_context.append(iteration_context)
        return iteration_context

    def update_memory_with_observation(
        self,
        agent_payload: dict[str, Any],
    ) -> None:
        task_id = self.memory.require_task_state().current_task_id
        iteration_context = self.append_iteration_context(
            role=ObservationIterationRole.OBSERVATION_PLAN,
            content=agent_payload,
        )
        observe_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.OBSERVATION_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="observe_runtime",
            payload=iteration_context.model_dump(mode="json"),
            task_id=task_id,
        )
        self.memory.insert_event(observe_event)

    def update_memory_with_review(self, agent_payload: dict[str, Any]) -> None:
        task_id = self.memory.require_task_state().current_task_id
        iteration_context = self.append_iteration_context(
            role=ObservationIterationRole.REVIEW,
            content=agent_payload,
        )
        observe_review_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.OBSERVATION_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="observe_review",
            payload=iteration_context.model_dump(mode="json"),
            task_id=task_id,
        )
        self.memory.insert_event(observe_review_event)

    async def run_observation_review(
        self,
        observation: ObservationResult,
    ) -> ObservationReviewResult:
        client = self.model.get_agent_client()
        context = {
            "observation_context": (
                self.review_context_builder.build_runtime_context()
            ),
            "observation_result": observation.model_dump(mode="json"),
            "prev_state_context": self.prev_state_context,
            "iteration": {
                "current": self.current_iteration,
                "max": self.max_iterations,
            },
            "prev_iteration_context": [
                item.model_dump(mode="json")
                for item in self.prev_iteration_context
            ],
        }

        raw_response = await client.send(
            [
                {
                    "role": "user",
                    "content": json.dumps(context, indent=2),
                }
            ],
            OBSERVATION_REVIEW_PROMPT,
            observation_review_result_adapter.json_schema(),
        )

        result = observation_review_result_adapter.validate_json(raw_response)
        self.update_memory_with_review(result.model_dump(mode="json"))
        return result

    async def run_observation(self) -> ObservationResult:
        client = self.model.get_agent_client()
        context = {
            "observation_context": self.context_builder.build_runtime_context(),
            "prev_state_context": self.prev_state_context,
            "iteration": {
                "current": self.current_iteration,
                "max": self.max_iterations,
            },
            "prev_iteration_context": [
                item.model_dump(mode="json")
                for item in self.prev_iteration_context
            ],
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
        self.update_memory_with_observation(result.model_dump(mode="json"))

        environment_state = await self.get_current_environment_state()
        hardware_state = await self.get_current_hardware_state()
        self.update_memory(environment_state, hardware_state)

        return result
