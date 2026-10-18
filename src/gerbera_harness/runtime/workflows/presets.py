from importlib.resources import files
from pathlib import Path

from gerbera_harness.runtime.contracts import WorkflowNode
from gerbera_harness.runtime.nodes import default_node_registry
from gerbera_harness.runtime.state_machine.base import StateMachine
from gerbera_harness.runtime.state_machine.builder import CompiledWorkflow, WorkflowBuilder
from gerbera_harness.runtime.state_machine.loader import WorkflowLoader


def load_preset(name: str) -> CompiledWorkflow:
    root = Path(str(files("gerbera_harness.runtime.workflows")))
    return WorkflowLoader(root, default_node_registry()).load(Path(name) / "workflow.json")


def simple_workflow() -> CompiledWorkflow:
    return load_preset("simple")


def structured_workflow() -> CompiledWorkflow:
    return StructuredExecutionWorkflow().compile()


class StructuredExecutionWorkflow(StateMachine):
    def __init__(self, strategies: dict[str, WorkflowNode] | None = None) -> None:
        self.strategies = dict(strategies or {})

    def define_workflow(self) -> WorkflowBuilder:
        preset = load_preset("structured")
        unknown = self.strategies.keys() - preset.nodes.keys()
        if unknown:
            raise ValueError(f"Unknown structured stages: {sorted(unknown)}")
        definition = preset.definition
        builder = WorkflowBuilder(definition.name)
        builder.with_interface(definition.interface).with_limits(definition.limits)
        for name, node in preset.nodes.items():
            builder.add_node(
                name, self.strategies.get(name, node), definition.nodes[name],
            )
        for transition in definition.transitions:
            builder.add_transition(transition)
        return builder


class StructuredWorkflowBuilder:
    def __init__(self) -> None:
        self.strategies: dict[str, WorkflowNode] = {}

    def with_stage(self, name: str, strategy: WorkflowNode) -> "StructuredWorkflowBuilder":
        self.strategies[name] = strategy
        return self

    def build(self) -> StructuredExecutionWorkflow:
        return StructuredExecutionWorkflow(self.strategies)
