from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from gerbera_harness.runtime.contracts import HarnessServices, EventHandler
from gerbera_harness.runtime.events import EventPublisher
from gerbera_harness.runtime.extensions import HarnessExtension, HarnessRegistry
from gerbera_harness.runtime.nodes import default_node_registry
from gerbera_harness.runtime.state_machine.base import StateMachine
from gerbera_harness.runtime.state_machine.builder import CompiledWorkflow
from gerbera_harness.runtime.state_machine.engine import (
    ExecutionServices, WorkflowExecution,
)
from gerbera_harness.runtime.state_machine.loader import WorkflowLoader
from gerbera_harness.runtime.state_machine.schemas import (
    RunRequest, RunResult, WorkflowState,
)
from gerbera_harness.tools.sources import CompositeToolSource


class BaseHarness(ABC):
    @abstractmethod
    def create_execution(
        self, request: RunRequest, handler: EventHandler,
    ) -> WorkflowExecution:
        """Bind a validated workflow to isolated state and injected services."""

    async def run(self, request: RunRequest) -> RunResult:
        async def ignore_event(event) -> None:
            return None

        return await self.create_execution(request, ignore_event).run()


@dataclass(frozen=True)
class Harness(BaseHarness):
    workflows: dict[str, CompiledWorkflow]
    services: HarnessServices
    registry: HarnessRegistry

    def create_execution(
        self, request: RunRequest, handler: EventHandler,
    ) -> WorkflowExecution:
        if request.workflow not in self.workflows:
            raise ValueError(f"Unknown workflow: {request.workflow}")
        workflow = self.workflows[request.workflow]
        publisher = EventPublisher((handler, *self.registry.event_handlers))
        return WorkflowExecution(
            workflow,
            ExecutionServices(self.services, publisher, tuple(self.registry.transforms)),
            WorkflowState(
                workflow=request.workflow,
                input=request.input,
                metadata=request.metadata,
            ),
        )

    @classmethod
    def simple(cls, services: HarnessServices) -> "Harness":
        from gerbera_harness.runtime.workflows.presets import simple_workflow

        return HarnessBuilder(services).with_workflow(simple_workflow()).build()

    @classmethod
    def structured(cls, services: HarnessServices) -> "Harness":
        from gerbera_harness.runtime.workflows.presets import structured_workflow

        return HarnessBuilder(services).with_workflow(structured_workflow()).build()


class HarnessBuilder:
    def __init__(self, services: HarnessServices) -> None:
        self.services = services
        self.registry = HarnessRegistry(default_node_registry())
        self.workflows: dict[str, CompiledWorkflow] = {}
        self.extension_names: set[str] = set()

    def with_extension(self, extension: HarnessExtension) -> "HarnessBuilder":
        name = getattr(extension, "name", type(extension).__qualname__)
        if name in self.extension_names:
            raise ValueError(f"Duplicate extension: {name}")
        extension.register(self.registry)
        self.extension_names.add(name)
        return self

    def with_workflow(
        self, workflow: CompiledWorkflow | StateMachine,
    ) -> "HarnessBuilder":
        compiled = workflow.compile() if isinstance(workflow, StateMachine) else workflow
        name = compiled.definition.name
        if name in self.workflows:
            raise ValueError(f"Duplicate workflow: {name}")
        self.workflows[name] = compiled
        return self

    def with_workflow_file(self, path: Path, root: Path) -> "HarnessBuilder":
        return self.with_workflow(WorkflowLoader(root, self.registry.nodes).load(path))

    def build(self) -> Harness:
        if not self.workflows:
            raise ValueError("At least one workflow is required")
        services = HarnessServices(
            model=self.services.model,
            tools=CompositeToolSource((
                self.services.tools, *self.registry.tool_sources,
            )),
            resources=self.services.resources,
        )

        async def tool_catalog(state: WorkflowState):
            return {"tools": [spec.model_dump() for spec in await services.tools.list_tools()]}

        registry = HarnessRegistry(
            nodes=self.registry.nodes,
            tool_sources=list(self.registry.tool_sources),
            transforms=[tool_catalog, *self.registry.transforms],
            event_handlers=list(self.registry.event_handlers),
        )
        return Harness(dict(self.workflows), services, registry)
