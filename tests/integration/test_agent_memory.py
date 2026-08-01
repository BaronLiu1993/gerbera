import asyncio
import json

from gerbera_harness.agent_runtime.agent_runtime import Agent
from gerbera_harness.agent.driver.main_loop import (
    LoopStateEnum,
    Session,
)


class FakeInitialisationProcess:
    mcp_url = "https://hardware.example.com/mcp"
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
                "hypothesis": {
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
                                        "Review the collected temperature "
                                        "readings."
                                    ),
                                    "action_type": "review",
                                    "analysis_goal": (
                                        "Compare temperature by heater state."
                                    ),
                                    "independent_variables": [
                                        {
                                            "variable": "heater_state",
                                            "table_name": (
                                                "temperature_readings"
                                            ),
                                            "unit": None,
                                            "type": "bool",
                                        }
                                    ],
                                    "dependent_variables": [
                                        {
                                            "variable": "temperature",
                                            "table_name": (
                                                "temperature_readings"
                                            ),
                                            "unit": "celsius",
                                            "type": "float",
                                        }
                                    ],
                                    "expected": (
                                        "Temperature is higher when the "
                                        "heater is on."
                                    ),
                                }
                            ],
                        },
                    },
                },
                "clarifying_questions": [],
            }
        )


class FakeModel:
    def get_agent_client(self) -> FakeClient:
        return FakeClient()


class FakeExecutionProcess:
    def __init__(self, mcp_url: str, actions_list: list) -> None:
        self.mcp_url = mcp_url
        self.actions_list = actions_list

    async def run_workflow(self) -> list:
        return []


def test_agent_runs_initialisation_end_to_end(monkeypatch) -> None:
    monkeypatch.setattr(
        "gerbera_harness.agent_runtime.agent_runtime.ExecutionProcess",
        FakeExecutionProcess,
    )
    session = Session()
    agent = Agent(
        session=session,
        model=FakeModel(),
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    result = asyncio.run(agent.run_agent("Test the sensor"))

    assert result is None
    assert session.state.state is LoopStateEnum.EXECUTION
