import asyncio
import json

import pytest

from gerbera_harness.agent.driver.main_loop.schema.initialisation import (
    Answer,
    Question,
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
