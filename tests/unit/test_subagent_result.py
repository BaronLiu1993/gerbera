from gerbera_harness.agent.driver.main_loop.states.base import (
    ExecuteDecisionEnum,
)
from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.agent_runtime import SubAgentResult


def test_subagent_result_contains_terminal_execution_data() -> None:
    error = ExecuteErrorSchema(
        event_name="move_arm",
        event_type=ExecutionTypeEnum.AGENT,
        position=1,
        error="Arm movement failed",
    )

    result = SubAgentResult(
        decision=ExecuteDecisionEnum.FAILED,
        errors=[error],
        turns_completed=3,
    )

    assert result.decision is ExecuteDecisionEnum.FAILED
    assert result.errors == [error]
    assert result.turns_completed == 3
