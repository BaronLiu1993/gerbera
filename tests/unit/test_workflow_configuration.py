import asyncio
from dataclasses import replace
import json
from pathlib import Path

import pytest
from pydantic import Field

from gerbera_harness.runtime.contracts import HarnessServices
from gerbera_harness.runtime.harness import HarnessBuilder
from gerbera_harness.runtime.nodes import NodeFactory, default_node_registry
from gerbera_harness.runtime.nodes.transform import TransformNode, TransformConfig
from gerbera_harness.runtime.state_machine.builder import WorkflowBuilder
from gerbera_harness.runtime.state_machine.loader import WorkflowLoader
from gerbera_harness.runtime.state_machine.schemas import (
    NodeDefinition, RunRequest, Transition, WorkflowLimits, WorkflowSchema,
)
from gerbera_harness.runtime.state_machine.validation import validate_workflow
from gerbera_harness.runtime.workflows.presets import simple_workflow
from gerbera_harness.tools.sources import LocalToolSource


def workflow_payload():
    return {
        "name": "custom",
        "nodes": {"answer": {
            "type": "transform", "config": {"constants": {"message": "hello"}},
            "outcomes": ["complete"],
        }},
        "transitions": [
            {"from": "__entry__", "outcome": "start", "to": "answer"},
            {"from": "answer", "outcome": "complete", "to": "__exit__", "terminal": {
                "status": "succeeded", "output": {"message": "/nodes/answer/output/message"},
            }},
        ],
    }


@pytest.mark.parametrize("mutation", [
    lambda data: data["transitions"].append(data["transitions"][0]),
    lambda data: data["transitions"][0].update({"to": "missing"}),
    lambda data: data["nodes"]["answer"].update({"outcomes": ["unknown"]}),
    lambda data: data["nodes"].update({"__entry__": data["nodes"]["answer"]}),
    lambda data: data["transitions"][1].pop("terminal"),
    lambda data: data["nodes"]["answer"].update({"outputs": {"": "/input/secret"}}),
])
def test_invalid_graph_is_rejected_during_loading(tmp_path: Path, mutation):
    data = workflow_payload()
    mutation(data)
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(data))

    with pytest.raises(ValueError):
        WorkflowLoader(tmp_path, default_node_registry()).load(Path(path.name))


def test_subworkflow_can_be_composed_from_json(tmp_path: Path):
    child = workflow_payload()
    child["name"] = "child"
    (tmp_path / "child.json").write_text(json.dumps(child))
    parent = workflow_payload()
    parent["nodes"] = {"answer": {
        "type": "subworkflow", "config": {"workflow": "child.json"},
        "outcomes": ["succeeded"],
    }}
    parent["transitions"][1]["outcome"] = "succeeded"
    parent["transitions"][1]["terminal"]["output"]["message"] = "/nodes/answer/output/output/message"
    (tmp_path / "parent.json").write_text(json.dumps(parent))
    workflow = WorkflowLoader(tmp_path, default_node_registry()).load(Path("parent.json"))
    harness = HarnessBuilder(HarnessServices(object(), LocalToolSource())).with_workflow(workflow).build()

    result = asyncio.run(harness.run(RunRequest(workflow="custom", input={})))

    assert result.output == {"message": "hello"}


def test_recursive_subworkflow_is_rejected(tmp_path: Path):
    payload = workflow_payload()
    payload["nodes"]["answer"] = {
        "type": "subworkflow", "config": {"workflow": "workflow.json"},
        "outcomes": ["succeeded"],
    }
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="Recursive"):
        WorkflowLoader(tmp_path, default_node_registry()).load(Path(path.name))


def test_custom_factory_configuration_is_validated_before_build(tmp_path: Path):
    class CustomConfig(WorkflowSchema):
        message: str = Field(min_length=1)

    registry = default_node_registry()
    registry.register(NodeFactory(
        "custom", CustomConfig,
        lambda config: TransformNode(TransformConfig(constants={"message": config.message})),
    ))
    payload = workflow_payload()
    payload["nodes"]["answer"].update({"type": "custom", "config": {"message": ""}})
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        WorkflowLoader(tmp_path, registry).load(Path(path.name))


def test_cycles_are_bounded_by_global_step_limit():
    class Repeat:
        async def execute(self, state, context):
            from gerbera_harness.runtime.state_machine.schemas import NodeResult

            return NodeResult(outcome="again")

    workflow = (
        WorkflowBuilder("repeat")
        .with_limits(WorkflowLimits(maximum_steps=2))
        .add_node("repeat", Repeat(), NodeDefinition(type="custom", outcomes=("again", "done")))
        .add_transition(Transition.model_validate({"from": "__entry__", "outcome": "start", "to": "repeat"}))
        .add_transition(Transition.model_validate({"from": "repeat", "outcome": "again", "to": "repeat"}))
        .add_transition(Transition.model_validate({"from": "repeat", "outcome": "done", "to": "__exit__", "terminal": {"status": "succeeded"}}))
        .build()
    )
    harness = HarnessBuilder(HarnessServices(object(), LocalToolSource())).with_workflow(workflow).build()

    result = asyncio.run(harness.run(RunRequest(workflow="repeat", input={})))

    assert (result.error.code, result.steps) == ("step_limit", 2)
