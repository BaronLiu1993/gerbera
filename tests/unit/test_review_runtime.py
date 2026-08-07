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
        self.system_prompt = None

    async def send(self, messages, system_prompt, output_schema) -> str:
        self.output_schema = output_schema
        self.system_prompt = system_prompt
        return json.dumps(self.response)


class FakeModel:
    def __init__(self, response: dict) -> None:
        self.client = FakeClient(response)

    def get_agent_client(self) -> FakeClient:
        return self.client


class FakeContextBuilder:
    def build(self) -> list[dict]:
        return [{"role": "user", "content": "Review the evidence."}]


def response_envelope(response: dict) -> dict:
    return {"response": response}


def test_review_runtime_uses_review_response_schema() -> None:
    model = FakeModel(
        response_envelope(
            {
                "decision": "accepted",
                "next_state": None,
                "feedback": [],
            }
        )
    )
    memory = Memory(goal="Validate the workflow")
    runtime = ReviewRuntime(
        model=model,
        memory=memory,
        context_builder=FakeContextBuilder(),
    )

    result = asyncio.run(runtime.run_review())

    assert result.decision is ReviewDecisionEnum.ACCEPTED
    assert result.requested_next_state is None
    assert result.feedback == []
    assert model.client.output_schema == (
        ReviewResponseSchema.model_json_schema()
    )
    assert model.client.system_prompt.startswith("# Review")
    assert memory.messages[-1]["role"] == "assistant"


def test_review_response_owns_transition_validation() -> None:
    envelope = ReviewResponseSchema.model_validate(
        response_envelope(
            {
                "decision": ReviewDecisionEnum.REJECTED,
                "next_state": None,
                "feedback": ["Collect more evidence."],
            }
        )
    )

    assert envelope.response.next_state is None

    with pytest.raises(ValidationError):
        ReviewResponseSchema.model_validate(
            response_envelope(
                {
                    "decision": ReviewDecisionEnum.REJECTED,
                    "next_state": LoopStateEnum.INITIALISATION,
                    "feedback": ["Collect more evidence."],
                }
            )
        )

    with pytest.raises(ValidationError):
        ReviewResponseSchema.model_validate(
            response_envelope(
                {
                    "decision": ReviewDecisionEnum.ACCEPTED,
                    "next_state": LoopStateEnum.INITIALISATION,
                    "feedback": [],
                }
            )
        )

    replan = ReviewResponseSchema.model_validate(
        response_envelope(
            {
                "decision": ReviewDecisionEnum.REPLAN,
                "next_state": LoopStateEnum.INITIALISATION,
                "feedback": ["Create another plan."],
            }
        )
    )
    assert replan.response.next_state is LoopStateEnum.INITIALISATION


def test_review_schema_has_an_object_root() -> None:
    schema = ReviewResponseSchema.model_json_schema()

    assert schema["type"] == "object"
    assert "anyOf" not in schema
    assert "anyOf" in schema["properties"]["response"]


def test_review_runtime_fails_on_invalid_transition() -> None:
    runtime = ReviewRuntime(
        model=FakeModel(
            response_envelope(
                {
                    "decision": "accepted",
                    "next_state": "initialisation",
                    "feedback": [],
                }
            )
        ),
        memory=Memory(goal="Validate the workflow"),
        context_builder=FakeContextBuilder(),
    )

    with pytest.raises(ValidationError):
        asyncio.run(runtime.run_review())
