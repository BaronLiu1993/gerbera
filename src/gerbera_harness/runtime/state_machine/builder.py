from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from gerbera_harness.runtime.contracts import WorkflowNode
from gerbera_harness.runtime.state_machine.schemas import (
    NodeDefinition, Transition, WorkflowDefinition, WorkflowInterface,
    WorkflowLimits,
)
from gerbera_harness.runtime.state_machine.validation import validate_workflow


@dataclass(frozen=True)
class CompiledWorkflow:
    definition: WorkflowDefinition
    nodes: Mapping[str, WorkflowNode]
    transitions: Mapping[tuple[str, str], Transition]


class WorkflowBuilder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.definitions: dict[str, NodeDefinition] = {}
        self.strategies: dict[str, WorkflowNode] = {}
        self.transitions: list[Transition] = []
        self.interface = WorkflowInterface()
        self.limits = WorkflowLimits()

    def with_interface(self, interface: WorkflowInterface) -> "WorkflowBuilder":
        self.interface = interface
        return self

    def with_limits(self, limits: WorkflowLimits) -> "WorkflowBuilder":
        self.limits = limits
        return self

    def add_node(
        self, name: str, strategy: WorkflowNode, definition: NodeDefinition,
    ) -> "WorkflowBuilder":
        if name in self.strategies:
            raise ValueError(f"Duplicate node: {name}")
        self.strategies[name] = strategy
        self.definitions[name] = definition.model_copy(deep=True)
        return self

    def add_transition(self, transition: Transition) -> "WorkflowBuilder":
        self.transitions.append(transition.model_copy(deep=True))
        return self

    def build(self) -> CompiledWorkflow:
        definition = WorkflowDefinition(
            name=self.name,
            interface=self.interface,
            nodes=dict(self.definitions),
            transitions=tuple(self.transitions),
            limits=self.limits,
        ).model_copy(deep=True)
        validate_workflow(definition)
        return CompiledWorkflow(
            definition=definition,
            nodes=MappingProxyType(dict(self.strategies)),
            transitions=MappingProxyType({
                (item.source, item.outcome): item
                for item in definition.transitions
            }),
        )
