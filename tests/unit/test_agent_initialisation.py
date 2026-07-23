import asyncio
import json

import pytest

from gerbera_sdk.harness.agent.agent import Agent
from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import LoopStateEnum


class FakeInitialisationProcess:
    available_tool_names = frozenset()

    async def run(self, user_prompt: str) -> str:
        return f"# Experiment Context\n\n## Objective\n\n{user_prompt}"


class FakeClient:
    def __init__(self, response: dict | list[dict]) -> None:
        responses = response if isinstance(response, list) else [response]
        self.responses = iter(responses)
        self.system_prompt = None

    def send(self, messages, system_prompt, valid_schema) -> str:
        self.system_prompt = system_prompt
        return json.dumps(next(self.responses))


class FakeModel:
    def __init__(self, response: dict | list[dict]) -> None:
        self.client = FakeClient(response)

    def get_agent_client(self) -> FakeClient:
        return self.client


def hypothesis_response() -> dict:
    return {
        "hypothesis": "Heating increases temperature.",
        "dependent_variables": ["temperature"],
        "independent_variables": ["heater_state"],
        "controlled_variables": ["room_temperature"],
        "assumptions": ["The sensor is calibrated."],
        "methods": [],
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


def test_agent_accepts_valid_initialisation() -> None:
    session = Session()
    model = FakeModel(
        {
            "decision": "accepted",
            "next_state": "execution",
            "response": hypothesis_response(),
        }
    )
    agent = Agent(
        session=session,
        model=model,
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    hypothesis = asyncio.run(agent.run_agent("Test the heater."))

    assert hypothesis is not None
    assert hypothesis.hypothesis == "Heating increases temperature."
    assert session.state.state is LoopStateEnum.INITIALISATION
    assert model.client.system_prompt.startswith("# Initialisation")


def test_agent_retries_rejected_initialisation() -> None:
    session = Session()
    agent = Agent(
        session=session,
        model=FakeModel(
            [
                {
                    "decision": "rejected",
                    "next_state": "initialisation",
                    "response": None,
                },
                {
                    "decision": "accepted",
                    "next_state": "execution",
                    "response": hypothesis_response(),
                },
            ]
        ),
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    hypothesis = asyncio.run(agent.run_agent("Test the heater."))

    assert hypothesis is not None
    assert session.state.state is LoopStateEnum.INITIALISATION
    assert len(agent.messages) == 2


def test_agent_rejects_unknown_execute_target() -> None:
    response = hypothesis_response()
    response["methods"] = [
        {
            "description": "Collect a reading.",
            "name": "Read sensor",
            "steps": [
                {
                    "description": "Read the sensor.",
                    "action": {
                        "type": "execute",
                        "target": "invented_tool",
                        "params": [],
                    },
                    "expected": None,
                }
            ],
        }
    ]
    process = FakeInitialisationProcess()
    process.available_tool_names = frozenset({"read_temperature"})
    agent = Agent(
        session=Session(),
        model=FakeModel(
            {
                "decision": "accepted",
                "next_state": "execution",
                "response": response,
            }
        ),
        memory=object(),
        initialisation_process=process,
    )

    with pytest.raises(ValueError, match="invented_tool"):
        asyncio.run(agent.run_agent("Test the heater."))
