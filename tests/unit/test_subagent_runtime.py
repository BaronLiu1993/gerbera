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
    PlanState,
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


class ReadyObservationRuntime:
    async def run_observation(self) -> ObservationStatusEnum:
        return ObservationStatusEnum.READY


class ReadyPlanningRuntime:
    async def run_planning(self) -> PlanningStatusEnum:
        return PlanningStatusEnum.READY


class CompletePlanningRuntime:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    async def run_planning(self) -> PlanningStatusEnum:
        self.memory.complete_task()
        return PlanningStatusEnum.COMPLETE


class SequencedObservationRuntime:
    def __init__(self) -> None:
        self.statuses = [
            ObservationStatusEnum.READY,
            ObservationStatusEnum.COMPLETE,
        ]

    async def run_observation(self) -> ObservationStatusEnum:
        return self.statuses.pop(0)


class HangingObservationRuntime:
    async def run_observation(self) -> ObservationStatusEnum:
        await asyncio.Event().wait()
        return ObservationStatusEnum.READY


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
    assert runtime.turns_completed == 2


def test_subagent_stops_after_maximum_completed_turns(monkeypatch) -> None:
    act_runtime = FakeActRuntime(ToolCallStatusEnum.SUCCESS)
    monkeypatch.setattr(
        SubAgentRuntime,
        "act_runtime",
        property(lambda self: act_runtime),
    )
    monkeypatch.setattr(
        SubAgentRuntime,
        "observation_runtime",
        property(lambda self: ReadyObservationRuntime()),
    )
    monkeypatch.setattr(
        SubAgentRuntime,
        "planning_runtime",
        property(lambda self: ReadyPlanningRuntime()),
    )
    runtime = SubAgentRuntime(
        session=Session(state=ActState()),
        model=SimpleNamespace(),
        memory=planning_memory(),
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=1,
        max_turns=3,
        action_plan=planned_action(),
    )

    with pytest.raises(RuntimeError, match="maximum of 3 turns"):
        asyncio.run(runtime.run_agent())

    assert runtime.turns_completed == 3
    assert isinstance(runtime.session.state, ActState)


def test_subagent_runs_observe_plan_act_observe_end_to_end(
    monkeypatch,
) -> None:
    observation_runtime = SequencedObservationRuntime()
    act_runtime = FakeActRuntime(ToolCallStatusEnum.SUCCESS)
    monkeypatch.setattr(
        SubAgentRuntime,
        "observation_runtime",
        property(lambda self: observation_runtime),
    )
    monkeypatch.setattr(
        SubAgentRuntime,
        "planning_runtime",
        property(lambda self: ReadyPlanningRuntime()),
    )
    monkeypatch.setattr(
        SubAgentRuntime,
        "act_runtime",
        property(lambda self: act_runtime),
    )
    runtime = SubAgentRuntime(
        session=Session(),
        model=SimpleNamespace(),
        memory=planning_memory(),
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=1,
        action_plan=planned_action(),
    )

    asyncio.run(runtime.run_agent())

    assert runtime.turns_completed == 4
    assert runtime.memory.tasks[0].status == "completed"
    assert act_runtime.action is runtime.action_plan


def test_subagent_rejects_invalid_maximum_turns() -> None:
    with pytest.raises(ValueError, match="max_turns must be at least 1"):
        SubAgentRuntime(
            session=Session(),
            model=SimpleNamespace(),
            memory=planning_memory(),
            mcp_url="https://hardware.example.com/mcp",
            timeout_seconds=1,
            max_turns=0,
        )


def test_subagent_times_out_an_unfinished_task(monkeypatch) -> None:
    monkeypatch.setattr(
        SubAgentRuntime,
        "observation_runtime",
        property(lambda self: HangingObservationRuntime()),
    )
    runtime = SubAgentRuntime(
        session=Session(),
        model=SimpleNamespace(),
        memory=planning_memory(),
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=0.001,
    )

    with pytest.raises(TimeoutError, match="timed out after 0.001 seconds"):
        asyncio.run(runtime.run_agent())

    assert runtime.turns_completed == 0


def test_subagent_rejects_invalid_timeout() -> None:
    with pytest.raises(
        ValueError,
        match="timeout_seconds must be greater than 0",
    ):
        SubAgentRuntime(
            session=Session(),
            model=SimpleNamespace(),
            memory=planning_memory(),
            mcp_url="https://hardware.example.com/mcp",
            timeout_seconds=0,
        )


def test_subagent_stops_when_planning_completes(monkeypatch) -> None:
    memory = planning_memory()
    planning_runtime = CompletePlanningRuntime(memory)
    monkeypatch.setattr(
        SubAgentRuntime,
        "planning_runtime",
        property(lambda self: planning_runtime),
    )
    runtime = SubAgentRuntime(
        session=Session(state=PlanState()),
        model=SimpleNamespace(),
        memory=memory,
        mcp_url="https://hardware.example.com/mcp",
        timeout_seconds=1,
    )

    asyncio.run(runtime.run_agent())

    assert runtime.turns_completed == 1
    assert memory.tasks[0].status == "completed"


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
