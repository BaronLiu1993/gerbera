import asyncio
import json

from gerbera_sdk.harness.agent.agent import Agent
from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import (
    Initialisation,
    LoopStateEnum,
)


class FakeInitialisationProcess:
    available_tool_names = frozenset()

    async def run(self, user_prompt: str) -> str:
        return f"# Experiment Context\n\n## Objective\n\n{user_prompt}"


class FakeClient:
    def __init__(self, response: dict | list[dict]) -> None:
        responses = response if isinstance(response, list) else [response]
        self.responses = iter(responses)
        self.system_prompt = None
        self.valid_schema = None

    def send(self, messages, system_prompt, valid_schema) -> str:
        self.system_prompt = system_prompt
        self.valid_schema = valid_schema
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
        "method": {
            "description": "Collect and review temperature readings.",
            "name": "heating_test",
            "steps": [
                {
                    "description": "Review the collected temperature readings.",
                    "action_type": "review",
                    "analysis_goal": "Compare temperature by heater state.",
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
                    "expected": "Temperature is higher when the heater is on.",
                }
            ],
        },
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

    result = asyncio.run(agent.run_agent("Test the heater."))

    assert result is None
    assert session.state.state is LoopStateEnum.INITIALISATION
    assert model.client.system_prompt.startswith("# Initialisation")
    assert model.client.valid_schema == Initialisation.valid_schema


def test_agent_stops_after_rejected_initialisation() -> None:
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

    result = asyncio.run(agent.run_agent("Test the heater."))

    assert result is None
    assert session.state.state is LoopStateEnum.INITIALISATION
    assert len(agent.messages) == 1
