from dataclasses import dataclass
from pathlib import Path

from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningStatusEnum,
    planning_adapter,
    planning_review_adapter,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.main_loop.utils import append_message


PROMPT_DIRECTORY = Path(__file__).resolve().parents[2] / "prompts" / "sub"
PLANNING_PROMPT = (PROMPT_DIRECTORY / "PLANNING.md").read_text().strip()
PLANNING_REVIEW_PROMPT = (
    PROMPT_DIRECTORY / "PLANNING_REVIEW.md"
).read_text().strip()


@dataclass
class PlanningRuntime:
    model: Model
    messages: list[dict[str, object]]

    async def run_planning(self) -> PlanningStatusEnum:
        client = self.model.get_agent_client()

        while True:
            raw_response = client.send(
                self.messages,
                PLANNING_PROMPT,
                planning_adapter.json_schema(),
            )
            response = planning_adapter.validate_json(raw_response)

            append_message(
                self.messages,
                role="assistant",
                content=response.model_dump_json(),
            )

            raw_review = client.send(
                self.messages,
                PLANNING_REVIEW_PROMPT,
                planning_review_adapter.json_schema(),
            )
            review = planning_review_adapter.validate_json(raw_review)

            if review.status in {
                PlanningStatusEnum.READY,
                PlanningStatusEnum.BLOCKED,
            }:
                break

            append_message(
                self.messages,
                role="user",
                content=review.model_dump_json(),
            )

        return review.status
