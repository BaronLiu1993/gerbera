import json
from dataclasses import dataclass
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
    PlanningAction,
    PlanningDecision,
    PlanningResult,
)

PLANNING_PROMPT = load_prompt(PromptTypeEnum.SUB, "PLANNING.md")


@dataclass
class PlanningRuntime:
    model: Model
    memory: Memory
    prev_state_context: str
    context_builder: PlanningContextBuilder
    max_attempts: int = 3

    def update_memory_with_plan(self, agent_payload: dict[str, Any]) -> None:
        task_id = self.memory.require_task_state().current_task_id
        plan_event = EventSchema(
            session_id=self.memory.session_id,
            event_type=EventTypeEnum.PLAN_CREATED,
            source_type=SourceTypeEnum.AGENT,
            source_name="planning_runtime",
            payload=agent_payload,
            task_id=task_id,
        )
        self.memory.insert_event(plan_event)

    async def run_planning(self) -> PlanningResult:
        client = self.model.get_agent_client()
        context = {
            "planning_context": self.context_builder.build_runtime_context(),
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
                PLANNING_PROMPT,
                PlanningAction.model_json_schema(),
            )
            
            action = PlanningAction.model_validate_json(raw_response)

            self.update_memory_with_plan(action.model_dump(mode="json"))

            return PlanningResult(
                context=action.context,
                actions=action.actions,
                result=PlanningDecision.SUCCESS,
            )
        # Happy path for now 
        return PlanningResult(
            context="FAILED TASK",
            actions=[],
            result=PlanningDecision.FAIL,
        )
