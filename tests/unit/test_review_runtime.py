import asyncio
import json

import pytest
from pydantic import ValidationError

from gerbera_harness.agent.driver.main_loop import (
    LoopStateEnum,
    ReviewDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.review import (
    ReviewResponseSchema,
)
from gerbera_harness.agent_runtime.main_loop.review_runtime import (
    ReviewRuntime,
)
from gerbera_harness.memory import Memory


class FakeClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.output_schema = None

    async def send(self, messages, system_prompt, output_schema) -> str:
        self.output_schema = output_schema
        return json.dumps(self.response)


class FakeModel:
    def __init__(self, response: dict) -> None:
        self.client = FakeClient(response)

    def get_agent_client(self) -> FakeClient:
        return self.client


class FakeContextBuilder:
    def build(self) -> list[dict]:
        return [{"role": "user", "content": "Review the evidence."}]


def test_review_runtime_uses_review_response_schema() -> None:
    model = FakeModel(
        {
            "decision": "accepted",
            "next_state": None,
            "hypothesis": None,
        }
    )
    memory = Memory(goal="Validate the workflow")
    runtime = ReviewRuntime(
        model=model,
        memory=memory,
        context_builder=FakeContextBuilder(),
    )

    result = asyncio.run(runtime.run_review("Review the completed work."))

    assert result.decision is ReviewDecisionEnum.ACCEPTED
    assert result.requested_next_state is None
    assert model.client.output_schema == (
        ReviewResponseSchema.model_json_schema()
    )
    assert memory.messages[-1]["role"] == "assistant"


def test_review_response_owns_transition_validation() -> None:
    response = ReviewResponseSchema(
        decision=ReviewDecisionEnum.REJECTED,
        next_state=LoopStateEnum.INITIALISATION,
        hypothesis=None,
    )

    assert response.next_state is LoopStateEnum.INITIALISATION

    with pytest.raises(ValidationError):
        ReviewResponseSchema(
            decision=ReviewDecisionEnum.REJECTED,
            next_state=None,
            hypothesis=None,
        )
