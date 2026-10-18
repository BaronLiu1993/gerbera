from gerbera_harness.runtime.nodes.condition import ConditionConfig, ConditionNode
from gerbera_harness.runtime.nodes.prompt import PromptConfig, PromptNode
from gerbera_harness.runtime.nodes.registry import NodeFactory, NodeRegistry
from gerbera_harness.runtime.nodes.tools import ToolExecutionConfig, ToolExecutionNode
from gerbera_harness.runtime.nodes.transform import TransformConfig, TransformNode
from gerbera_harness.runtime.workflows.observation import (
    ObservationConfig, ObservationNode,
)


def default_node_registry() -> NodeRegistry:
    registry = NodeRegistry()
    for node_type, schema, strategy in (
        ("agent", AgentConfig, AgentNode),
        ("prompt", PromptConfig, PromptNode),
        ("tool_execution", ToolExecutionConfig, ToolExecutionNode),
        ("condition", ConditionConfig, ConditionNode),
        ("transform", TransformConfig, TransformNode),
        ("observation", ObservationConfig, ObservationNode),
    ):
        registry.register(NodeFactory(node_type, schema, strategy))
    return registry


__all__ = ["NodeFactory", "NodeRegistry", "default_node_registry"]
from gerbera_harness.runtime.nodes.agent import AgentConfig, AgentNode
