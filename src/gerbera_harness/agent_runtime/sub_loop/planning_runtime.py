from collections.abc import Callable
from dataclasses import dataclass

from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningExecuteActionSchema,
    PlanningResponseSchema,
    PlanningReviewSchema,
    PlanningStatusEnum,
    planning_adapter,
    planning_review_adapter,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.subagent_context import (
    SubAgentPromptContextBuilder,
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
    context_builder: SubAgentPromptContextBuilder
    messages: list[dict[str, object]]
    on_action_planned: Callable[[PlanningExecuteActionSchema], None]

    async def run_planning(self) -> PlanningStatusEnum:
        client = self.model.get_agent_client()

        raw_response = await client.send(
            self.context_builder.build(),
            PLANNING_PROMPT,
            PlanningResponseSchema.model_json_schema(),
        )
        response = planning_adapter.validate_json(raw_response)
        self.on_action_planned(response.action)

        self.messages.append(
            {"role": "assistant", "content": response.model_dump_json()}
        )

        raw_review = await client.send(
            self.context_builder.build(),
            PLANNING_REVIEW_PROMPT,
            PlanningReviewSchema.model_json_schema(),
        )
        review = planning_review_adapter.validate_json(raw_review)

        if review.status is PlanningStatusEnum.COMPLETE:
            return review.status

        if review.status in {
            PlanningStatusEnum.READY,
            PlanningStatusEnum.BLOCKED,
        }:
            return review.status

        self.messages.append(
            {"role": "user", "content": review.model_dump_json()}
        )

        return PlanningStatusEnum.CONTINUE
