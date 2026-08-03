import asyncio
import json
from types import SimpleNamespace

from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationStatusEnum,
)
from gerbera_harness.agent_runtime.sub_loop import observe_runtime
from gerbera_harness.agent_runtime.sub_loop.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.memory import EventTypeEnum, Memory


class FakeMCPClient:
    def __init__(self, mcp_url: str) -> None:
        assert mcp_url == "https://hardware.example.com/mcp"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        pass

    async def list_tools(self) -> list:
        return [SimpleNamespace(name="read_temperature")]

    async def call_tool(
        self,
        name: str,
        arguments: dict,
        allowed_tool_names: frozenset[str],
    ) -> dict[str, object]:
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
    def get_agent_client(self) -> FakeClient:
        return FakeClient()


def test_observation_updates_shared_memory(monkeypatch) -> None:
    monkeypatch.setattr(observe_runtime, "MCPClient", FakeMCPClient)
    memory = Memory(goal="Read the temperature")
    runtime = ObservationRuntime(
        model=FakeModel(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
    )

    status = asyncio.run(runtime.run_observation())

    assert status is ObservationStatusEnum.COMPLETE
    assert memory.world_state_ledger[-1].state == {
        "temperature": {"value": 22.5, "unit": "celsius"}
    }
    assert [event.event_type for event in memory.event_ledger] == [
        EventTypeEnum.TOOL_CALL,
        EventTypeEnum.WORLD_STATE_UPDATED,
    ]
    assert len(memory.messages) == 3
