from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel

from gerbera_harness.runtime.contracts import WorkflowNode
from gerbera_harness.runtime.state_machine.schemas import NodeDefinition


@dataclass(frozen=True)
class NodeFactory:
    node_type: str
    config_schema: type[BaseModel]
    build: Callable[[BaseModel], WorkflowNode]


@dataclass
class NodeRegistry:
    factories: dict[str, NodeFactory] = field(default_factory=dict)

    def register(self, factory: NodeFactory) -> None:
        if factory.node_type in self.factories:
            raise ValueError(f"Node type already registered: {factory.node_type}")
        self.factories[factory.node_type] = factory

    def build(self, definition: NodeDefinition) -> WorkflowNode:
        try:
            factory = self.factories[definition.type]
        except KeyError as error:
            raise ValueError(f"Unknown node type: {definition.type}") from error
        config = factory.config_schema.model_validate(definition.config)
        return factory.build(config)

    def config_schema(self, node_type: str) -> dict:
        if node_type not in self.factories:
            raise ValueError(f"Unknown node type: {node_type}")
        return self.factories[node_type].config_schema.model_json_schema()
