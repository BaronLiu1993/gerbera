from collections.abc import Callable
from dataclasses import dataclass

from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningExecuteActionSchema,
    PlanningStatusEnum,
    planning_adapter,
    planning_review_adapter,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.memory import (
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
)
from gerbera_harness.prompts import PromptTypeEnum, load_prompt


PLANNING_PROMPT = load_prompt(PromptTypeEnum.SUB, "PLANNING.md")
PLANNING_REVIEW_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "PLANNING_REVIEW.md",
)


@dataclass
class PlanningRuntime:
    model: Model
    memory: Memory
    on_action_planned: Callable[[PlanningExecuteActionSchema], None]

    async def run_planning(self) -> PlanningStatusEnum:
        client = self.model.get_agent_client()

        while True:
            raw_response = client.send(
                self.memory.messages,
                PLANNING_PROMPT,
                planning_adapter.json_schema(),
            )
            response = planning_adapter.validate_json(raw_response)
            self.on_action_planned(response.action)

            self.memory.append_message(
                "assistant",
                response.model_dump_json(),
            )

            raw_review = client.send(
                self.memory.messages,
                PLANNING_REVIEW_PROMPT,
                planning_review_adapter.json_schema(),
            )
            review = planning_review_adapter.validate_json(raw_review)

            if review.status in {
                PlanningStatusEnum.READY,
                PlanningStatusEnum.BLOCKED,
            }:
                if review.status is PlanningStatusEnum.READY:
                    self._record_selected_action(response.action)
                break

            self.memory.append_message(
                "user",
                review.model_dump_json(),
            )

        return review.status

    def _record_selected_action(
        self,
        action: PlanningExecuteActionSchema,
    ) -> None:
        self.memory.append_event(
            event_type=EventTypeEnum.ACTION_SELECTED,
            source_type=SourceTypeEnum.MODEL,
            payload={"action": action.model_dump(mode="json")},
        )
