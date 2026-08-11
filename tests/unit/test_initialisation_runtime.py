import asyncio
import json

import pytest

from gerbera_harness.agent.driver.main_loop.schema.initialisation import (
    Answer,
    Question,
)
from gerbera_harness.agent.driver.main_loop.states.base import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.agent_runtime.context_builder import (
    InitialisationContextBuilder,
)
from gerbera_harness.agent_runtime.main_loop.initialisation_runtime import (
    InitialisationRuntime,
)
from gerbera_harness.memory import Memory


def runtime_with_questions() -> tuple[InitialisationRuntime, Question]:
    question = Question(
        question="Which room should be tested?",
        options=["lab", "office"],
    )
    runtime = InitialisationRuntime(
        model=object(),
        memory=Memory(goal="Test the heater"),
        context_builder=object(),
        process=object(),
        clarifying_questions=[question],
    )
    return runtime, question


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.messages = []

    async def send(self, messages, system_prompt, output_schema) -> str:
        self.messages.append(messages)
        return json.dumps(self.responses.pop(0))


class FakeModel:
    def __init__(self, responses: list[dict]) -> None:
        self.client = FakeClient(responses)

    def get_agent_client(self) -> FakeClient:
        return self.client


class FakeInitialisationProcess:
    async def run(self, user_prompt: str) -> str:
        return f"# Experiment Context\n\n## Objective\n{user_prompt}"


def hypothesis_response() -> dict:
    return {
        "hypothesis": "Heating increases temperature.",
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "controlled_variables": ["room_temperature"],
        "assumptions": ["The sensor is calibrated."],
        "method": {
            "description": "Collect and review temperature readings.",
            "name": "heating_test",
            "execute_steps": [
                {
                    "goal": "Turn on the heater and prepare for readings.",
                    "action_type": "execute",
                    "actions": [
                        {
                            "description": "Turn on the heater.",
                            "action_type": "execute",
                            "execution_type": "discrete",
                            "start_offset_seconds": 0,
                            "dependent_variables": ["temperature"],
                            "independent_variables": ["heater_state"],
                            "forward_tool_call": "turn_on_heater",
                            "params": [],
                        }
                    ],
                },
            ],
            "final_review": {
                "action_type": "review",
                "actions": [
                    {
                        "description": (
                            "Review the collected temperature readings."
                        ),
                        "action_type": "review",
                        "analysis_goal": (
                            "Compare temperature by heater state."
                        ),
                        "independent_variables": [
                            {
                                "variable": "heater_state",
                                "table_name": "temperature_readings",
                                "unit": None,
                                "type": "bool",
                            }
                        ],
                        "dependent_variables": [
                            {
                                "variable": "temperature",
                                "table_name": "temperature_readings",
                                "unit": "celsius",
                                "type": "float",
                            }
                        ],
                        "expected": (
                            "Temperature is higher when the heater is on."
                        ),
                    }
                ],
            },
        },
    }


def accepted_response(hypothesis: dict) -> dict:
    return {
        "response": {
            "decision": "accepted",
            "next_state": "execution",
            "hypothesis": hypothesis,
            "issues": [],
            "rejection_reasons": [],
            "clarifying_questions": [],
        }
    }


def test_clarifying_questions_remain_ordered_for_the_ui() -> None:
    runtime, question = runtime_with_questions()

    assert runtime.get_questions() == [question]


def test_submit_answers_validates_question_ids() -> None:
    runtime, question = runtime_with_questions()

    asyncio.run(
        runtime.submit_answers(
            [
                Answer(
                    question_id=question.question_id,
                    question="Untrusted duplicate question text",
                    answer="lab",
                )
            ]
        )
    )

    submitted = json.loads(runtime.memory.messages[-1]["content"])
    assert submitted["clarification_answers"] == [
        {
            "question_id": question.question_id,
            "question": "Which room should be tested?",
            "answer": "lab",
        }
    ]

    with pytest.raises(
        ValueError,
        match="must match all clarifying question IDs",
    ):
        asyncio.run(
            runtime.submit_answers(
                [
                    Answer(
                        question_id="unknown",
                        question="Unknown",
                        answer="lab",
                    )
                ]
            )
        )


def test_initialisation_review_receives_explicit_candidate_hypothesis() -> None:
    hypothesis = hypothesis_response()
    model = FakeModel([hypothesis, accepted_response(hypothesis)])
    memory = Memory(goal="Test the heater")
    runtime = InitialisationRuntime(
        model=model,
        memory=memory,
        context_builder=InitialisationContextBuilder(
            memory=memory,
            context_window_size=20,
        ),
        process=FakeInitialisationProcess(),
    )

    result = asyncio.run(runtime.run_initial("Test the heater", []))

    review_context = json.loads(model.client.messages[1][0]["content"])
    assert review_context["runtime_context"]["candidate_hypothesis"] == (
        hypothesis
    )
    assert result.decision is InitialisationDecisionEnum.ACCEPTED
    assert result.requested_next_state is LoopStateEnum.EXECUTION


def test_initialisation_raises_when_hypothesis_generation_is_invalid() -> None:
    model = FakeModel([""])
    memory = Memory(goal="Test the heater")
    runtime = InitialisationRuntime(
        model=model,
        memory=memory,
        context_builder=InitialisationContextBuilder(
            memory=memory,
            context_window_size=20,
        ),
        process=FakeInitialisationProcess(),
    )

    with pytest.raises(
        RuntimeError,
        match="Initialisation did not produce a valid hypothesis",
    ):
        asyncio.run(runtime.run_initial("Test the heater", []))
