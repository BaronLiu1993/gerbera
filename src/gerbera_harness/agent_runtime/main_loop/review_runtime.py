from dataclasses import dataclass

from gerbera_harness.agent.driver.main_loop.schema.hypothesis import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.review import (
    ReviewResponseSchema,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    LoopStateEnum,
    ReviewDecisionEnum,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.context_builder import ContextBuilder
from gerbera_harness.memory import Memory


@dataclass(frozen=True)
class ReviewResult:
    decision: ReviewDecisionEnum
    requested_next_state: LoopStateEnum | None
    hypothesis: HypothesisSchema | None


@dataclass
class ReviewRuntime:
    model: Model
    memory: Memory
    context_builder: ContextBuilder
    max_attempts: int = 3

    async def run_review(self, system_prompt: str) -> ReviewResult:
        client = self.model.get_agent_client()

        for _ in range(self.max_attempts):
            raw_response = await client.send(
                self.context_builder.build(),
                system_prompt,
                ReviewResponseSchema.model_json_schema(),
            )

            response = ReviewResponseSchema.model_validate_json(raw_response)

            self.memory.append_message(
                "assistant",
                response.model_dump_json(),
            )

            if response.decision is ReviewDecisionEnum.ACCEPTED:
                # Return For now, if request next state is none it is terminal
                return ReviewResult(
                    decision=response.decision,
                    requested_next_state=None,
                    hypothesis=response.hypothesis,
                )
            elif response.decision is ReviewDecisionEnum.REPLAN:
                return ReviewResult(
                    decision=response.decision,
                    requested_next_state=response.requested_next_state,
                    hypothesis=response.hypothesis,
                )
            elif response.decision is ReviewDecisionEnum.REJECTED:
                return ReviewResult(
                    decision=response.decision,
                    requested_next_state=None,
                    hypothesis=response.hypothesis,
                )
            else:
                raise ValueError("Failed to ")
