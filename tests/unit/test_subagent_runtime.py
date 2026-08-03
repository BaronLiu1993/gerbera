import asyncio
from types import SimpleNamespace

import pytest

from gerbera_harness.agent.driver.subloop.schema.act import (
    ToolCallStatusEnum,
)
from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationStatusEnum,
)
from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningStatusEnum,
    PlanningResponseSchema,
)
from gerbera_harness.agent.driver.subloop.states import (
    ActState,
    ObserveState,
    Session,
)
from gerbera_harness.agent_runtime.subagent_runtime import SubAgentRuntime
from gerbera_harness.memory import EventTypeEnum, Memory, TaskSchema


class FakeHypothesis:
    def model_dump(self, *, mode: str) -> dict[str, object]:
        return {"hypothesis": "Motor speed follows the command"}


def planning_memory() -> Memory:
    memory = Memory(goal="Set the motor speed")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        TaskSchema.model_validate(
            {
                "status": "in_progress",
                "task": {
                    "goal": "Set the motor speed to 10",
                    "action_type": "execute",
                    "actions": [
                        {
                            "description": "Set the motor speed",
                            "action_type": "execute",
                            "execution_type": "discrete",
                            "start_offset_seconds": 0,
                            "dependent_variables": ["motor_speed"],
                            "independent_variables": ["requested_speed"],
                            "forward_tool_call": "set_motor",
                            "params": [],
                        }
                    ],
                },
            }
        )
    )
    memory.append_world_state({"motor_speed": 0})
    return memory


def planned_action():
    response = PlanningResponseSchema.model_validate(
        {
            "action": {
                "description": "Set the motor speed.",
                "action_type": "execute",
                "execution_type": "discrete",
                "start_offset_seconds": 0,
                "dependent_variables": ["motor_speed"],
                "independent_variables": ["requested_speed"],
                "forward_tool_call": "set_motor",
                "params": [
                    {
                        "variable": "speed",
                        "value": 10,
                        "unit": None,
                        "type": "int",
                    }
                ],
            }
        }
    )
    return response.action


class FakeActRuntime:
    def __init__(self, status: ToolCallStatusEnum) -> None:
        self.status = status
        self.action = None

    async def run_action(self, action) -> ToolCallStatusEnum:
        self.action = action
        return self.status


class FakeObservationRuntime:
    async def run_observation(self) -> ObservationStatusEnum:
        return ObservationStatusEnum.COMPLETE


@pytest.mark.parametrize("status", list(ToolCallStatusEnum))
def test_act_status_returns_control_to_observation(
    monkeypatch,
    status: ToolCallStatusEnum,
) -> None:
    act_runtime = FakeActRuntime(status)
    monkeypatch.setattr(
        SubAgentRuntime,
        "act_runtime",
        property(lambda self: act_runtime),
    )
    monkeypatch.setattr(
        SubAgentRuntime,
        "observation_runtime",
        property(lambda self: FakeObservationRuntime()),
    )
    runtime = SubAgentRuntime(
        session=Session(state=ActState()),
        model=SimpleNamespace(),
        memory=planning_memory(),
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=1,
        action_plan=planned_action(),
    )

    asyncio.run(runtime.run_agent())

    assert act_runtime.action.forward_tool_call == "set_motor"
    assert isinstance(runtime.session.state, ObserveState)
    assert runtime.memory.tasks[0].status == "completed"


class FakePlanningClient:
    def __init__(self) -> None:
        self.responses = [
            PlanningResponseSchema(action=planned_action()).model_dump_json(),
            '{"status":"ready","feedback":"Action is feasible"}',
        ]

    def send(self, messages, system_prompt, valid_schema) -> str:
        return self.responses.pop(0)


class FakePlanningModel:
    def get_agent_client(self) -> FakePlanningClient:
        return FakePlanningClient()


def test_subagent_runtimes_share_memory() -> None:
    memory = Memory(goal="Set the motor speed")
    runtime = SubAgentRuntime(
        session=Session(),
        model=FakePlanningModel(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=1,
    )

    assert runtime.observation_runtime.memory is memory
    assert runtime.planning_runtime.memory is memory
    assert runtime.act_runtime.memory is memory


def test_planning_runtime_updates_action_plan() -> None:
    runtime = SubAgentRuntime(
        session=Session(),
        model=FakePlanningModel(),
        memory=planning_memory(),
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=1,
    )

    status = asyncio.run(runtime.planning_runtime.run_planning())

    assert status is PlanningStatusEnum.READY
    assert runtime.action_plan is not None
    assert runtime.action_plan.forward_tool_call == "set_motor"
    assert runtime.memory.event_ledger[-1].event_type is (
        EventTypeEnum.ACTION_SELECTED
    )
