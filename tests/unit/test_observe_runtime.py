import asyncio
import json
from types import SimpleNamespace

from mcp.types import ToolAnnotations

from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationStatusEnum,
)
from gerbera_harness.agent_runtime.sub_loop import observe_runtime
from gerbera_harness.agent_runtime.context_builder import (
    ObservationContextBuilder,
)
from gerbera_harness.agent_runtime.sub_loop.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.memory import EventTypeEnum, Memory, TaskSchema


class FakeHypothesis:
    def model_dump(self, *, mode: str) -> dict[str, object]:
        return {"hypothesis": "Temperature can be measured"}


def current_task() -> TaskSchema:
    return TaskSchema.model_validate(
        {
            "status": "in_progress",
            "task": {
                "goal": "Read the current temperature",
                "action_type": "execute",
                "actions": [
                    {
                        "description": "Read the temperature sensor",
                        "action_type": "execute",
                        "execution_type": "discrete",
                        "start_offset_seconds": 0,
                        "dependent_variables": ["temperature"],
                        "independent_variables": ["sensor_state"],
                        "forward_tool_call": "read_temperature",
                        "params": [],
                    }
                ],
            },
        }
    )


class FakeMCPClient:
    def __init__(self, mcp_url: str) -> None:
        assert mcp_url == "https://hardware.example.com/mcp"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    async def list_tools(self) -> list:
        return [
            SimpleNamespace(
                name="read_temperature",
                annotations=ToolAnnotations(readOnlyHint=True),
            ),
            SimpleNamespace(
                name="set_heater",
                annotations=ToolAnnotations(readOnlyHint=False),
            ),
            SimpleNamespace(
                name="unclassified_tool",
                annotations=None,
            ),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict,
        allowed_tool_names: frozenset[str],
    ) -> dict[str, object]:
        assert allowed_tool_names == frozenset({"read_temperature"})
        assert name in allowed_tool_names
        return {"value": 22.5, "unit": "celsius"}


class FakeClient:
    def __init__(self) -> None:
        self.responses = [
            json.dumps(
                {
                    "observation": {
                        "content_type": "tool_call",
                        "tool_name": "read_temperature",
                        "arguments": {},
                    }
                }
            ),
            json.dumps(
                {
                    "observation": {
                        "content_type": "finish",
                        "reason": "Temperature was observed.",
                        "world_state": {
                            "temperature": {
                                "value": 22.5,
                                "unit": "celsius",
                            }
                        },
                    }
                }
            ),
            json.dumps(
                {
                    "status": "complete",
                    "feedback": "Objective is visibly achieved.",
                }
            ),
        ]

    def send(self, messages, system_prompt, valid_schema) -> str:
        return self.responses.pop(0)


class FakeModel:
    def __init__(self) -> None:
        self.client = FakeClient()

    def get_agent_client(self) -> FakeClient:
        return self.client


def test_observation_updates_shared_memory(monkeypatch) -> None:
    monkeypatch.setattr(observe_runtime, "MCPClient", FakeMCPClient)
    memory = Memory(goal="Read the temperature")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(current_task())
    runtime = ObservationRuntime(
        model=FakeModel(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
        context_builder=ObservationContextBuilder(
            memory=memory,
            context_window_size=20,
        ),
    )

    first_status = asyncio.run(runtime.run_observation())
    status = asyncio.run(runtime.run_observation())

    assert first_status is ObservationStatusEnum.CONTINUE
    assert status is ObservationStatusEnum.COMPLETE
    assert memory.world_state_ledger[-1].state == {
        "temperature": {"value": 22.5, "unit": "celsius"}
    }
    assert [event.event_type for event in memory.event_ledger] == [
        EventTypeEnum.TOOL_CALL,
        EventTypeEnum.WORLD_STATE_UPDATED,
    ]
    assert len(memory.messages) == 4
    assert json.loads(memory.messages[-1]["content"]) == {
        "observation_status": "complete"
    }
