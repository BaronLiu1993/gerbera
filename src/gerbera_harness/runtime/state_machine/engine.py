import asyncio
from dataclasses import dataclass

from pydantic import JsonValue

from gerbera_harness.runtime.contracts import (
    ContextTransform, HarnessServices, NodeContext,
)
from gerbera_harness.runtime.events import EventPublisher
from gerbera_harness.runtime.state_machine.bindings import (
    bind_inputs, enforce_json_limit, read_pointer, write_value,
)
from gerbera_harness.runtime.state_machine.boundaries import EntryNode, ExitNode
from gerbera_harness.runtime.state_machine.builder import CompiledWorkflow
from gerbera_harness.runtime.state_machine.schemas import (
    NodeResult, ReservedNode, RunResult, RunStatus, TerminalDefinition, TerminalStatus,
    WorkflowError, WorkflowEvent, WorkflowState,
)


class WorkflowFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error = WorkflowError(code=code, message=message)


@dataclass(frozen=True)
class ExecutionServices:
    services: HarnessServices
    publisher: EventPublisher
    transforms: tuple[ContextTransform, ...] = ()


@dataclass
class WorkflowExecution:
    workflow: CompiledWorkflow
    dependencies: ExecutionServices
    state: WorkflowState
    result: RunResult | None = None
    cancellation_requested: bool = False

    async def run(self) -> RunResult:
        definition = self.workflow.definition
        try:
            if self.cancellation_requested:
                raise asyncio.CancelledError()
            self.state = EntryNode(definition).enter(self.state)
            await self.emit("run.started")
            async with asyncio.timeout(definition.limits.maximum_duration_seconds):
                terminal = await self.traverse()
            try:
                result = ExitNode(definition).exit(self.state, terminal)
            except ValueError as error:
                raise WorkflowFailure(
                    "invalid_workflow_output", "Workflow output does not match its interface",
                ) from error
        except asyncio.CancelledError:
            result = self.failed_exit(
                RunStatus.CANCELLED,
                WorkflowError(code="cancelled", message="Run was cancelled"),
            )
        except TimeoutError:
            result = self.failed_exit(
                RunStatus.TIMED_OUT,
                WorkflowError(code="workflow_timeout", message="Run exceeded its time limit"),
            )
        except WorkflowFailure as failure:
            result = self.failed_exit(RunStatus.FAILED, failure.error)
        except Exception:
            result = self.failed_exit(
                RunStatus.FAILED,
                WorkflowError(code="workflow_failed", message="Workflow execution failed"),
            )
        self.result = result
        self.state = self.state.model_copy(update={
            "status": result.status, "current_node": ReservedNode.EXIT,
        })
        await self.emit(f"run.{result.status}")
        return result

    def failed_exit(self, status: TerminalStatus, error: WorkflowError) -> RunResult:
        return ExitNode(self.workflow.definition).exit(
            self.state, TerminalDefinition(status=status, error=error),
        )

    async def traverse(self) -> TerminalDefinition:
        current = ReservedNode.ENTRY
        outcome = "start"
        while True:
            await asyncio.sleep(0)
            if self.cancellation_requested:
                raise asyncio.CancelledError()
            transition = self.workflow.transitions[(current, outcome)]
            await self.emit("transition.selected", {
                "from": current, "outcome": outcome,
                "to": transition.destination,
            })
            if transition.destination == ReservedNode.EXIT:
                if transition.terminal is None:
                    raise WorkflowFailure("invalid_exit", "EXIT requires a terminal result")
                return transition.terminal
            if self.state.step >= self.workflow.definition.limits.maximum_steps:
                raise WorkflowFailure("step_limit", "Workflow exceeded its step limit")
            current = transition.destination
            self.state = self.state.model_copy(update={
                "current_node": current, "step": self.state.step + 1,
            })
            result = await self.execute_node(current)
            outcome = result.outcome

    async def execute_node(self, name: str) -> NodeResult:
        definition = self.workflow.definition.nodes[name]
        await self.emit("node.started")
        inputs = bind_inputs(definition.inputs, self.state.model_dump(mode="json"))
        extra = {}
        for transform in self.dependencies.transforms:
            extra.update(await transform(self.state.model_copy(deep=True)))
        enforce_json_limit(extra, self.workflow.definition.limits.maximum_state_bytes)
        context = NodeContext(
            services=self.dependencies.services,
            emit=self.dependencies.publisher.publish,
            input=inputs,
            extra=extra,
        )
        result = await self.invoke_node(name, context)
        if self.cancellation_requested:
            raise asyncio.CancelledError()
        if result.outcome not in definition.outcomes:
            raise WorkflowFailure("invalid_node_outcome", "Node returned an undeclared outcome")
        values = self.state.values
        for source, target in definition.outputs.items():
            values = write_value(values, target, read_pointer(result.output, source))
        self.state = self.state.model_copy(update={
            "values": values,
            "nodes": {**self.state.nodes, name: result.model_dump(mode="json")},
        }, deep=True)
        enforce_json_limit(
            self.state.model_dump(mode="json"),
            self.workflow.definition.limits.maximum_state_bytes,
        )
        await self.emit("node.completed", {"outcome": result.outcome})
        return result

    async def invoke_node(self, name: str, context: NodeContext) -> NodeResult:
        limits = self.workflow.definition.nodes[name].execution
        for attempt in range(limits.maximum_attempts):
            try:
                async with asyncio.timeout(limits.timeout_seconds):
                    result = await self.workflow.nodes[name].execute(
                        self.state.model_copy(deep=True), context,
                    )
                return NodeResult.model_validate(result)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                await self.emit("node.failed", {"attempt": attempt + 1})
                if attempt + 1 == limits.maximum_attempts:
                    code = "node_timeout" if isinstance(error, TimeoutError) else "node_failed"
                    raise WorkflowFailure(code, "Node execution failed") from error
        raise RuntimeError("Node attempt limit must be positive")

    async def emit(
        self, event_type: str, data: dict[str, JsonValue] | None = None,
    ) -> None:
        await self.dependencies.publisher.publish(WorkflowEvent(
            id=0, run_id=self.state.run_id, type=event_type,
            node=self.state.current_node, data=data or {},
            workflow=self.state.workflow,
        ))
