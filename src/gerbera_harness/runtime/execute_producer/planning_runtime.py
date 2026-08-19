from dataclasses import dataclass, field

from gerbera_harness.runtime.execute_producer.schemas import (
    PlanningResponseSchema,
    PlanningReviewSchema,
    PlanningStatusEnum,
    planning_adapter,
    planning_review_adapter,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.runtime.schemas.experiment import ExecuteActionGroupSchema
from gerbera_harness.runtime.execute_producer.context import (
    PlanningPromptContextBuilder,
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
    context_builder: PlanningPromptContextBuilder

    async def run_planning(self) -> PlanningStatusEnum:
        client = self.model.get_agent_client()
        context = self.context_builder.build()

        raw_response = await client.send(
            context,
            PLANNING_PROMPT,
            PlanningResponseSchema.model_json_schema(),
        )
        response = planning_adapter.validate_json(raw_response)

        raw_review = await client.send(
            [
                *context,
                {"role": "assistant", "content": raw_response},
            ],
            PLANNING_REVIEW_PROMPT,
            PlanningReviewSchema.model_json_schema(),
        )
        review = planning_review_adapter.validate_json(raw_review)

        if review.status is PlanningStatusEnum.COMPLETE:
            self.action_groups = response.action_groups
            return review.status

        if review.status in {
            PlanningStatusEnum.READY,
            PlanningStatusEnum.BLOCKED,
        }:
            if review.status is PlanningStatusEnum.READY:
                self.action_groups = response.action_groups
            return review.status

        return PlanningStatusEnum.CONTINUE
