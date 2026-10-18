from dataclasses import dataclass

from gerbera_harness.runtime.state_machine.bindings import (
    bind_inputs, enforce_json_limit, validate_document,
)
from gerbera_harness.runtime.state_machine.schemas import (
    ReservedNode, RunResult, RunStatus, TerminalDefinition,
    WorkflowDefinition, WorkflowState, utc_now,
)


@dataclass(frozen=True)
class EntryNode:
    definition: WorkflowDefinition

    def enter(self, state: WorkflowState) -> WorkflowState:
        validate_document(state.input, self.definition.interface.input_schema)
        enforce_json_limit(
            state.model_dump(mode="json"), self.definition.limits.maximum_state_bytes,
        )
        return state.model_copy(update={
            "status": RunStatus.RUNNING,
            "current_node": ReservedNode.ENTRY,
            "started_at": utc_now(),
        }, deep=True)


@dataclass(frozen=True)
class ExitNode:
    definition: WorkflowDefinition

    def exit(
        self, state: WorkflowState, terminal: TerminalDefinition,
    ) -> RunResult:
        output = None
        if terminal.status == RunStatus.SUCCEEDED:
            output = bind_inputs(terminal.output, state.model_dump(mode="json"))
            validate_document(output, self.definition.interface.output_schema)
        return RunResult(
            run_id=state.run_id,
            workflow=state.workflow,
            status=terminal.status,
            output=output,
            error=terminal.error,
            source_node=state.current_node,
            steps=state.step,
            started_at=state.started_at or utc_now(),
        )
