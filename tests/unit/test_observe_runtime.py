import asyncio
import json
from types import SimpleNamespace

from mcp.types import ToolAnnotations

from gerbera_sdk.firmware.firmware_schema import ToolStage, stage_metadata

from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationStatusEnum,
)
from gerbera_harness.agent_runtime.sub_loop import observe_runtime
from gerbera_harness.agent_runtime.subagent_context import (
    SubAgentContextBuilder,
    SubAgentPromptContextBuilder,
)
from gerbera_harness.agent_runtime.sub_loop.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.memory import Memory, TaskSchema
from gerbera_harness.tools.registry import LocalToolRegistry


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
                meta=None,
            ),
            SimpleNamespace(
                name="set_heater",
                annotations=ToolAnnotations(readOnlyHint=False),
                meta=None,
            ),
            SimpleNamespace(
                name="turn_on_temperature_stream",
                annotations=ToolAnnotations(readOnlyHint=False),
                meta=stage_metadata(ToolStage.OBSERVATION),
            ),
            SimpleNamespace(
                name="unclassified_tool",
                annotations=None,
                meta=None,
            ),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict,
        allowed_tool_names: frozenset[str],
    ) -> dict[str, object]:
        assert allowed_tool_names == frozenset(
            {
                "read_temperature",
                "set_heater",
                "turn_on_temperature_stream",
                "unclassified_tool",
            }
        )
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
                        "summary": "Temperature was observed.",
                        "result": {
                            "temperature": 22.5,
                            "unit": "celsius",
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

    async def send(self, messages, system_prompt, output_schema) -> str:
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
    messages = []
    observations = []
    tool_events = []
    context = SubAgentContextBuilder(memory).build(
        current_task=memory.tasks[0],
        workflow_position=0,
    )
    runtime = ObservationRuntime(
        model=FakeModel(),
        mcp_url="https://hardware.example.com/mcp",
        local_tool_registry=LocalToolRegistry(),
        context_builder=SubAgentPromptContextBuilder(
            context=context,
            phase="observation",
            messages=messages,
            observations=observations,
            tool_events=tool_events,
        ),
        messages=messages,
        observations=observations,
        tool_events=tool_events,
    )

    first_status = asyncio.run(runtime.run_observation())
    status = asyncio.run(runtime.run_observation())

    assert first_status is ObservationStatusEnum.CONTINUE
    assert status is ObservationStatusEnum.COMPLETE
    assert observations[-1].state == {
        "summary": "Temperature was observed.",
        "temperature": 22.5,
        "unit": "celsius",
    }
    assert len(tool_events) == 1
    assert tool_events[0]["tool_name"] == "read_temperature"
    assert len(messages) == 4
    assert json.loads(messages[-1]["content"]) == {
        "observation_status": "complete"
    }
