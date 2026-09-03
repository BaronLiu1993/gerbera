import json
from dataclasses import dataclass, field
from typing import Any

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import (
    EventSchema,
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
)
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.runtime.context import PlanningContextBuilder
from gerbera_harness.runtime.execute_producer.schemas import (
    PlanningIterationContext,
    PlanningIterationRole,
    PlanningResult,
    PlanningReviewResult,
    planning_result_adapter,
    planning_review_result_adapter,
)

PLANNING_PROMPT = load_prompt(PromptTypeEnum.SUB, "PLANNING.md")
PLANNING_REVIEW_PROMPT = load_prompt(PromptTypeEnum.SUB, "PLANNING_REVIEW.md")


@dataclass
class PlanningRuntime:
    model: Model
    memory: Memory
    prev_state_context: str
    context_builder: PlanningContextBuilder
    max_iterations: int
    prev_iteration_context: list[PlanningIterationContext] = field(
        default_factory=list
    )
    current_iteration: int = 1

    def append_iteration_context(
        self,
        role: PlanningIterationRole,
        content: dict[str, Any],
    ) -> PlanningIterationContext:
        iteration_context = PlanningIterationContext(
            iteration=self.current_iteration,
            role=role,
            content=content,
        )
        self.prev_iteration_context.append(iteration_context)
        return iteration_context

    def update_memory_with_plan(self, agent_payload: dict[str, Any]) -> None:
        task_id = self.memory.require_task_state().current_task_id
        iteration_context = self.append_iteration_context(
            role=PlanningIterationRole.PLAN,
            content=agent_payload,
        )
        plan_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.PLAN_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="planning_runtime",
            payload=iteration_context.model_dump(mode="json"),
            task_id=task_id,
        )
        self.memory.insert_event(plan_event)

    def update_memory_with_review(self, agent_payload: dict[str, Any]) -> None:
        task_id = self.memory.require_task_state().current_task_id
        iteration_context = self.append_iteration_context(
            role=PlanningIterationRole.REVIEW,
            content=agent_payload,
        )
        plan_review_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.PLAN_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="planning_runtime",
            payload=iteration_context.model_dump(mode="json"),
            task_id=task_id,
        )
        self.memory.insert_event(plan_review_event)

    async def run_planning(self) -> PlanningResult:
        client = self.model.get_agent_client()
        context = {
            "planning_context": self.context_builder.build_runtime_context(),
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
            PLANNING_PROMPT,
            planning_result_adapter.json_schema(),
        )

        result = planning_result_adapter.validate_json(raw_response)

        self.update_memory_with_plan(result.model_dump(mode="json"))
        return result

    async def run_planning_review(
        self,
        planning_result: PlanningResult,
    ) -> PlanningReviewResult:
        client = self.model.get_agent_client()
        context = {
            "planning_context": self.context_builder.build_runtime_context(),
            "planning_result": planning_result.model_dump(mode="json"),
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
            PLANNING_REVIEW_PROMPT,
            planning_review_result_adapter.json_schema(),
        )

        result = planning_review_result_adapter.validate_json(raw_response)
        self.update_memory_with_review(result.model_dump(mode="json"))
        return result
