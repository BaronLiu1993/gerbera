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

       