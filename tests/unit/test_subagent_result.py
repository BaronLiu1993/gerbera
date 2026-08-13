import pytest

from gerbera_harness.domain.session import (
    ExecuteDecisionEnum,
)
from gerbera_harness.domain.responses import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)
from gerbera_harness.workflows.adaptive.result import SubAgentResult


def test_subagent_result_contains_terminal_execution_data() -> None:
    error = ExecuteErrorSchema(
        event_name="move_arm",
        event_type=ExecutionTypeEnum.AGENT,
        position=1,
        error="Arm movement failed",
    )

    result = SubAgentResult(
        decision=ExecuteDecisionEnum.REJECTED,
        errors=[error],
        turns_completed=3,
    )

    assert result.decision is ExecuteDecisionEnum.REJECTED
    assert result.errors == [error]
    assert result.turns_completed == 3


def test_accepted_subagent_result_rejects_propagated_errors() -> None:
    error = ExecuteErrorSchema(
        event_name="move_arm",
        event_type=ExecutionTypeEnum.AGENT,
        position=1,
        error="Recovered movement failure",
    )

    with pytest.raises(
        ValueError,
        match="Accepted subagent results cannot contain errors",
    ):
        SubAgentResult(
            decision=ExecuteDecisionEnum.ACCEPTED,
            errors=[error],
            turns_completed=3,
        )
