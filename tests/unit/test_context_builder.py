import json
from dataclasses import dataclass

import pytest

from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent_runtime.context_builder import (
    ContextBuilder,
    ExecutionContextBuilder,
    InitialisationContextBuilder,
    ObservationContextBuilder,
    PlanningContextBuilder,
    ReviewContextBuilder,
)
from gerbera_harness.memory import (
    EventTypeEnum,
    Memory,
    SourceTypeEnum,
    TaskSchema,
)


def context_from(messages: list[dict[str, object]]) -> dict[str, object]:
    return json.loads(messages[0]["content"])["runtime_context"]


class FakeHypothesis:
    def model_dump(self, *, mode: str) -> dict[str, object]:
        return {"hypothesis": "Heating raises temperature"}


def task(status: str, goal: str, tool_name: str) -> TaskSchema:
    return TaskSchema.model_validate(
        {
            "status": status,
            "task": {
                "goal": goal,
                "action_type": "execute",
                "actions": [
                    {
                        "description": goal,
                        "action_type": "execute",
                        "execution_type": "discrete",
                        "start_offset_seconds": 0,
                        "dependent_variables": ["measured_temperature"],
                        "independent_variables": ["heater_state"],
                        "forward_tool_call": tool_name,
                        "params": [],
                    }
                ],
            },
        }
    )


def test_context_builder_is_abstract() -> None:
    with pytest.raises(TypeError):
        ContextBuilder(Memory(goal="Test"), 20)


def test_runtime_context_is_polymorphic() -> None:
    @dataclass(frozen=True)
    class TestContextBuilder(ContextBuilder):
        def build_runtime_context(self) -> dict[str, object]:
            return {"phase": "test"}

    context = TestContextBuilder(Memory(goal="Test"), 20).build()

    assert context_from(context) == {"phase": "test"}


def test_initialisation_context_contains_goal_and_bounded_history() -> None:
    memory = Memory(goal="Measure the temperature")
    memory.append_message("user", "first")
    memory.append_message("assistant", "second")

    context = InitialisationContextBuilder(memory, 1).build()

    assert context_from(context) == {
        "phase": "initialisation",
        "goal": "Measure the temperature",
    }
    assert context[1:] == [{"role": "assistant", "content": "second"}]


def test_review_context_allows_completed_workflow_state() -> None:
    memory = Memory(goal="Validate the completed workflow")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("completed", "Record the final temperature", "read_sensor")
    )

    context = context_from(ReviewContextBuilder(memory, 20).build())

    assert context["phase"] == "review"
    assert context["current_step"] is None
    assert context["completed_steps"][0]["status"] == "completed"


def test_execution_context_uses_latest_world_state(
) -> None:
    memory = Memory(goal="Set the motor speed")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("in_progress", "Set motor speed to 10", "set_motor")
    )
    memory.append_world_state({"motor_speed": 0})
    memory.append_world_state({"motor_speed": 10})

    context = context_from(ExecutionContextBuilder(memory, 20).build())

    assert context["phase"] == "execution"
    assert context["goal"] == "Set the motor speed"
    assert context["latest_world_state"]["state"] == {"motor_speed": 10}
    assert context["hypothesis"]["hypothesis"] == (
        "Heating raises temperature"
    )
    assert context["current_step_goal"] == "Set motor speed to 10"
    assert len(context["tasks"]) == 1


def test_observation_context_describes_current_step_and_prior_progress(
) -> None:
    memory = Memory(goal="Determine whether heating raises temperature")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("completed", "Record the baseline temperature", "read_sensor")
    )
    memory.tasks.append(
        task("in_progress", "Heat the sample to 30 C", "start_heater")
    )
    memory.append_event(
        event_type=EventTypeEnum.TASK_STATUS_CHANGED,
        source_type=SourceTypeEnum.RUNTIME,
        payload={"status": "completed", "step": 1},
    )
    memory.append_world_state({"temperature": 21.5})

    context = context_from(ObservationContextBuilder(memory, 20).build())

    assert context["phase"] == "observation"
    assert context["goal"] == (
        "Determine whether heating raises temperature"
    )
    assert context["current_step_goal"] == "Heat the sample to 30 C"
    assert context["current_step_number"] == 1
    assert context["current_step"]["status"] == "in_progress"
    assert context["completed_steps"][0]["task"]["goal"] == (
        "Record the baseline temperature"
    )
    assert context["recent_events"][0]["event_type"] == (
        "task_status_changed"
    )
    assert context["previous_world_states"][0]["state"] == {
        "temperature": 21.5
    }


def test_observation_context_requires_initialized_task_state() -> None:
    memory = Memory(goal="Observe the heater")

    with pytest.raises(AttributeError, match="model_dump"):
        ObservationContextBuilder(memory, 20).build()

    memory.tasks.append(
        task("in_progress", "Observe the heater", "read_heater")
    )

    with pytest.raises(AttributeError, match="model_dump"):
        ObservationContextBuilder(memory, 20).build()


def test_planning_context_uses_current_step_and_observed_world_state(
) -> None:
    memory = Memory(goal="Determine whether heating raises temperature")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("in_progress", "Heat the sample to 30 C", "start_heater")
    )
    memory.append_world_state({"temperature": 21.5})

    context = context_from(PlanningContextBuilder(memory, 20).build())

    assert context["phase"] == "planning"
    assert context["current_step_goal"] == "Heat the sample to 30 C"
    assert context["current_world_state"]["state"] == {
        "temperature": 21.5
    }
    assert context["previous_act_error"] is None


def test_planning_context_includes_previous_act_error() -> None:
    memory = Memory(goal="Set the motor speed")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("in_progress", "Set motor speed to 10", "set_motor")
    )
    memory.append_world_state({"motor_speed": 0})
    previous_error = ExecuteErrorSchema(
        event_name="set_motor",
        event_type=ExecutionTypeEnum.AGENT,
        position=2,
        error="motor rejected command",
    )

    context = context_from(
        PlanningContextBuilder(
            memory,
            20,
            previous_act_error=previous_error,
        ).build()
    )

    assert context["previous_act_error"] == previous_error.model_dump(
        mode="json"
    )


def test_planning_context_requires_an_observed_world_state() -> None:
    memory = Memory(goal="Plan heater action")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("in_progress", "Heat the sample", "start_heater")
    )

    with pytest.raises(IndexError):
        PlanningContextBuilder(memory, 20).build()


def test_context_build_does_not_mutate_memory() -> None:
    memory = Memory(goal="Observe the motor")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("in_progress", "Observe the motor", "read_motor")
    )
    memory.append_message("user", "observe")

    built_context = ExecutionContextBuilder(memory, 20).build()
    built_context[1]["content"] = "changed"

    assert memory.messages == [{"role": "user", "content": "observe"}]


def test_zero_context_window_excludes_message_history() -> None:
    memory = Memory(goal="Observe the motor")
    memory.current_hypothesis = FakeHypothesis()
    memory.tasks.append(
        task("in_progress", "Observe the motor", "read_motor")
    )
    memory.append_message("user", "observe")

    context = ExecutionContextBuilder(memory, 0).build()

    assert len(context) == 1
