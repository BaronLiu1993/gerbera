from dataclasses import dataclass, field
from typing import Protocol

from gerbera_harness.runtime.contracts import ContextTransform, EventHandler, ToolSource
from gerbera_harness.runtime.nodes.registry import NodeFactory, NodeRegistry


@dataclass
class HarnessRegistry:
    nodes: NodeRegistry
    tool_sources: list[ToolSource] = field(default_factory=list)
    transforms: list[ContextTransform] = field(default_factory=list)
    event_handlers: list[EventHandler] = field(default_factory=list)

    def register_node_factory(self, factory: NodeFactory) -> None:
        self.nodes.register(factory)

    def register_tool_source(self, source: ToolSource) -> None:
        self.tool_sources.append(source)

    def register_context_transform(self, transform: ContextTransform) -> None:
        self.transforms.append(transform)

    def subscribe(self, handler: EventHandler) -> None:
        self.event_handlers.append(handler)


class HarnessExtension(Protocol):
    def register(self, registry: HarnessRegistry) -> None: ...
