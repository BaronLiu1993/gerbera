import asyncio
from dataclasses import dataclass

from gerbera_harness.runtime.contracts import NodeContext
from gerbera_harness.runtime.events import EventPublisher
from gerbera_harness.runtime.state_machine.builder import CompiledWorkflow
from gerbera_harness.runtime.state_machine.engine import (
    ExecutionServices, WorkflowExecution,
)
from gerbera_harness.runtime.state_machine.schemas import NodeResult, WorkflowState


@dataclass(frozen=True)
class SubworkflowNode:
    workflow: CompiledWorkflow

    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult:
        async def publish_child(event) -> None:
            await context.emit(event.model_copy(update={
                "type": f"subworkflow.{event.type}",
                "node": f"{state.current_node}/{event.node}",
            }))

        child = WorkflowExecution(
            self.workflow,
            ExecutionServices(context.services, EventPublisher((publish_child,))),
            WorkflowState(
                run_id=state.run_id,
                workflow=self.workflow.definition.name,
                input=context.input,
            ),
        )
        result = await child.run()
        if result.status == "cancelled":
            raise asyncio.CancelledError()
        return NodeResult(outcome=result.status, output=result.model_dump(mode="json"))
