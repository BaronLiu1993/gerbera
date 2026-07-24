import asyncio
import json

from gerbera_sdk.harness.agent.agent import Agent
from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import LoopStateEnum


class FakeInitialisationProcess:
    available_tool_names = frozenset()

    async def run(self, user_prompt: str) -> str:
        return f"# Experiment Context\n\n## Objective\n\n{user_prompt}"


class FakeClient:
    def send(self, messages, system_prompt, valid_schema) -> str:
        assert messages[0]["content"].startswith("# Experiment Context")
        assert system_prompt.startswith("# Initialisation")
        return json.dumps(
            {
                "decision": "accepted",
                "next_state": "execution",
                "response": {
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
        )


class FakeModel:
    def get_agent_client(self) -> FakeClient:
        return FakeClient()


def test_agent_runs_initialisation_end_to_end() -> None:
    session = Session()
    agent = Agent(
        session=session,
        model=FakeModel(),
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    result = asyncio.run(agent.run_agent("Test the sensor"))

    assert result is None
    assert session.state.state is LoopStateEnum.INITIALISATION
