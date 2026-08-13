import asyncio
import copy
import json

import pytest
from pydantic import ValidationError

from gerbera_harness.workflows.coordinator import Agent
from gerbera_harness.domain.responses import (
    Answer,
)
from gerbera_harness.domain.session import (
    Initialisation,
    LoopStateEnum,
    Session,
)
from gerbera_harness.domain.responses import (
    InitialisationResponseSchema,
)


class FakeInitialisationProcess:
    mcp_url = "https://hardware.example.com/mcp"
    available_tool_names = frozenset()

    async def run(self, user_prompt: str) -> str:
        return f"# Experiment Context\n\n## Objective\n\n{user_prompt}"


class FakeClient:
    def __init__(self, response: dict | list[dict]) -> None:
        responses = response if isinstance(response, list) else [response]
        self.responses = iter(responses)
        self.system_prompt = None
        self.system_prompts = []
        self.output_schema = None

    async def send(self, messages, system_prompt, output_schema) -> str:
        self.system_prompt = system_prompt
        self.system_prompts.append(system_prompt)
        self.output_schema = output_schema
        return json.dumps(next(self.responses))


class FakeModel:
    def __init__(self, response: dict | list[dict]) -> None:
        self.client = FakeClient(response)

    def get_agent_client(self) -> FakeClient:
        return self.client


class FakeExecutionProcess:
    instances = []

    def __init__(self, mcp_url: str, actions_list: list) -> None:
        self.mcp_url = mcp_url
        self.actions_list = actions_list
        self.ran = False
        type(self).instances.append(self)

    async def run_workflow(self) -> list:
        self.ran = True
        return []


def hypothesis_response() -> dict:
    return {
        "hypothesis": "Heating increases temperature.",
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "controlled_variables": ["room_temperature"],
        "assumptions": ["The sensor is calibrated."],
        "clarifying_questions": [],
        "method": {
            "description": "Collect and review temperature readings.",
            "name": "heating_test",
            "execute_steps": [
                {
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


def accepted_response(hypothesis: dict | None = None) -> dict:
    return {
        "decision": "accepted",
        "next_state": "execution",
        "hypothesis": hypothesis or hypothesis_response(),
        "clarifying_questions": [],
    }


def test_agent_prepares_initialisation_context_without_transitioning() -> None:
    session = Session()
    initial_state = session.state
    agent = Agent(
        session=session,
        model=object(),
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    context = asyncio.run(
        agent.prepare_initialisation_context("Test the heater.")
    )

    assert "Test the heater." in context
    assert agent.messages == [{"role": "user", "content": context}]
    assert session.state is initial_state


def test_agent_accepts_valid_initialisation(monkeypatch) -> None:
    FakeExecutionProcess.instances = []
    monkeypatch.setattr(
        "gerbera_harness.workflows.coordinator.ExecutionProcess",
        FakeExecutionProcess,
    )
    session = Session()
    response = accepted_response()
    model = FakeModel([response, response])
    agent = Agent(
        session=session,
        model=model,
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    result = asyncio.run(agent.run_agent("Test the heater."))

    assert result is None
    assert session.state.state is LoopStateEnum.EXECUTION
    assert model.client.system_prompt.startswith("# Initialisation")
    assert len(model.client.system_prompts) == 2
    assert model.client.system_prompts[1].startswith(
        "# Initialisation Hypothesis Review"
    )
    assert model.client.output_schema == (
        InitialisationResponseSchema.model_json_schema()
    )
    assert len(FakeExecutionProcess.instances) == 1
    execution = FakeExecutionProcess.instances[0]
    assert execution.mcp_url == "https://hardware.example.com/mcp"
    assert len(execution.actions_list) == 1
    assert execution.ran


def test_agent_rejects_invalid_candidate_without_retry() -> None:
    invalid_hypothesis = hypothesis_response()
    invalid_hypothesis["method"].pop("final_review")
    model = FakeModel(accepted_response(invalid_hypothesis))
    agent = Agent(
        session=Session(),
        model=model,
        initialisation_process=FakeInitialisationProcess(),
    )

    with pytest.raises(ValidationError):
        asyncio.run(agent.run_agent("Test the heater."))

    assert agent.session.state.state is LoopStateEnum.INITIALISATION


def test_agent_stops_after_rejected_initialisation() -> None:
    session = Session()
    agent = Agent(
        session=session,
        model=FakeModel(
            [
                {
                    "decision": "rejected",
                    "next_state": "initialisation",
                    "hypothesis": None,
                    "clarifying_questions": [],
                },
            ]
        ),
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    result = asyncio.run(agent.run_agent("Test the heater."))

    assert result is None
    assert session.state.state is LoopStateEnum.INITIALISATION
    assert len(agent.messages) == 2


def test_reviewer_can_apply_a_small_hypothesis_fix(monkeypatch) -> None:
    FakeExecutionProcess.instances = []
    monkeypatch.setattr(
        "gerbera_harness.workflows.coordinator.ExecutionProcess",
        FakeExecutionProcess,
    )
    corrected_hypothesis = copy.deepcopy(hypothesis_response())
    corrected_hypothesis["hypothesis"] = (
        "Turning on the heater increases measured temperature."
    )
    agent = Agent(
        session=Session(),
        model=FakeModel(
            [
                accepted_response(),
                accepted_response(corrected_hypothesis),
            ]
        ),
        initialisation_process=FakeInitialisationProcess(),
    )

    asyncio.run(agent.run_agent("Test the heater."))

    assert agent.current_hypothesis is not None
    assert agent.current_hypothesis.hypothesis == (
        "Turning on the heater increases measured temperature."
    )


def test_clarification_questions_and_answers_are_kept_in_memory() -> None:
    agent = Agent(
        session=Session(),
        model=FakeModel(
            {
                "decision": "clarify",
                "next_state": "initialisation",
                "hypothesis": None,
                "clarifying_questions": [
                    {
                        "question": "Which room should be tested?",
                        "options": ["lab", "office"],
                    }
                ],
            }
        ),
        initialisation_process=FakeInitialisationProcess(),
    )

    asyncio.run(agent.run_agent("Test the heater."))

    question_id, question = next(
        iter(agent.clarification_questions.items())
    )
    assert question.question == "Which room should be tested?"

    asyncio.run(
        agent.submit_answers(
            [Answer(question_id=question_id, answer="lab")]
        )
    )

    submitted = json.loads(agent.messages[-1]["content"])
    assert submitted["clarification_answers"] == [
        {
            "question_id": question_id,
            "question": "Which room should be tested?",
            "options": ["lab", "office"],
            "answer": "lab",
        }
    ]
