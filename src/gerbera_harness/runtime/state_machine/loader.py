import json
from pathlib import Path

from pydantic import Field

from gerbera_harness.runtime.nodes.registry import NodeRegistry
from gerbera_harness.runtime.nodes.subworkflow import SubworkflowNode
from gerbera_harness.runtime.contracts import WorkflowNode
from gerbera_harness.runtime.state_machine.builder import (
    CompiledWorkflow, WorkflowBuilder,
)
from gerbera_harness.runtime.state_machine.schemas import (
    NodeDefinition, WorkflowDefinition, WorkflowSchema,
)

MAXIMUM_CONFIG_BYTES = 1_000_000
MAXIMUM_SUBWORKFLOW_DEPTH = 10


def unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


class SubworkflowConfig(WorkflowSchema):
    workflow: str = Field(min_length=1)


class WorkflowLoader:
    def __init__(self, root: Path, registry: NodeRegistry) -> None:
        self.root = root.resolve(strict=True)
        self.registry = registry

    def resolve(self, path: Path) -> Path:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            raise ValueError(f"Workflow file escapes configuration root: {path.name}")
        if resolved.stat().st_size > MAXIMUM_CONFIG_BYTES:
            raise ValueError(f"Workflow file is too large: {path.name}")
        return resolved

    def read_json(self, path: Path) -> dict:
        resolved = self.resolve(path)
        value = json.loads(resolved.read_text(), object_pairs_hook=unique_json_object)
        if not isinstance(value, dict):
            raise ValueError(f"Workflow configuration must be an object: {path.name}")
        return value

    def load(self, path: Path) -> CompiledWorkflow:
        return self.load_nested(self.root / path, ())

    def load_nested(
        self, path: Path, ancestors: tuple[Path, ...],
    ) -> CompiledWorkflow:
        path = self.resolve(path)
        if path in ancestors or len(ancestors) >= MAXIMUM_SUBWORKFLOW_DEPTH:
            raise ValueError("Recursive or excessively nested subworkflow")
        payload = self.read_json(path)
        nodes = payload.get("nodes")
        if not isinstance(nodes, dict):
            raise ValueError("Workflow nodes must be an object")
        expanded = {}
        node_directories = {}
        for name, reference in nodes.items():
            node_path = path
            if isinstance(reference, str):
                node_path = self.resolve(path.parent / reference)
            node_data = self.read_json(node_path) if isinstance(reference, str) else reference
            expanded[name] = self.expand_prompt(node_data, node_path.parent)
            node_directories[name] = node_path.parent
        definition = WorkflowDefinition.model_validate({**payload, "nodes": expanded})
        builder = WorkflowBuilder(definition.name)
        builder.with_interface(definition.interface).with_limits(definition.limits)
        for name, node in definition.nodes.items():
            strategy = self.build_node(node, node_directories[name], (*ancestors, path))
            builder.add_node(name, strategy, node)
        for transition in definition.transitions:
            builder.add_transition(transition)
        return builder.build()

    def expand_prompt(self, node_data: dict, directory: Path) -> dict:
        if not isinstance(node_data, dict):
            raise ValueError("Node configuration must be an object")
        config = dict(node_data.get("config", {}))
        prompt_file = config.pop("prompt_file", None)
        if prompt_file is not None:
            if node_data.get("type") != "prompt" or "prompt" in config:
                raise ValueError("prompt_file is exclusive to prompt nodes")
            prompt_path = self.resolve(directory / prompt_file)
            config["prompt"] = prompt_path.read_text()
        return {**node_data, "config": config}

    def build_node(
        self, node: NodeDefinition, directory: Path, ancestors: tuple[Path, ...],
    ) -> WorkflowNode:
        if node.type != "subworkflow":
            return self.registry.build(node)
        config = SubworkflowConfig.model_validate(node.config)
        child = self.load_nested(directory / config.workflow, ancestors)
        return SubworkflowNode(child)
