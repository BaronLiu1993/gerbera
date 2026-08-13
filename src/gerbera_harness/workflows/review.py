from dataclasses import dataclass

from gerbera_harness.domain.responses import (
    ReviewResponseSchema,
)
from gerbera_harness.domain.session import (
    LoopStateEnum,
    ReviewDecisionEnum,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.workflows.context import ContextBuilder
from gerbera_harness.memory import Memory
from gerbera_harness.prompts import PromptTypeEnum, load_prompt

REVIEW_PROMPT = load_prompt(PromptTypeEnum.MAIN, "REVIEW.md")


@dataclass(frozen=True)
class ReviewResult:
    decision: ReviewDecisionEnum
    requested_next_state: LoopStateEnum | None
    feedback: list[str]


@dataclass
class ReviewRuntime:
    model: Model
    memory: Memory
    context_builder: ContextBuilder
    max_attempts: int = 3

    async def run_review(self) -> ReviewResult:
        client = self.model.get_agent_client()
        review_context = self.context_builder.build()

        for _ in range(self.max_attempts):
            raw_response = await client.send(
                review_context,
                REVIEW_PROMPT,
                ReviewResponseSchema.model_json_schema(),
            )
            envelope = ReviewResponseSchema.model_validate_json(raw_response)
            response = envelope.response

            self.memory.append_message(
                "assistant",
                response.model_dump_json(),
            )

            return ReviewResult(
                decision=response.decision,
                requested_next_state=response.next_state,
                feedback=list(response.feedback),
            )

        raise RuntimeError("Review completed without producing a result")
