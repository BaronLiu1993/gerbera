import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from gerbera_harness.runtime.contracts import HarnessServices
from gerbera_harness.runtime.harness import Harness, HarnessBuilder
from gerbera_harness.runtime.nodes import default_node_registry
from gerbera_harness.runtime.runs import RunLimits, RunManager
from gerbera_harness.runtime.state_machine.builder import WorkflowBuilder
from gerbera_harness.runtime.state_machine.loader import WorkflowLoader
from gerbera_harness.runtime.state_machine.schemas import (
    ExecutionLimits, NodeDefinition, NodeResult, RunRequest,
    RunStatus, TerminalDefinition, Transition, WorkflowInterface, WorkflowLimits,
)
from gerbera_harness.runtime.workflows.presets import (
    StructuredWorkflowBuilder, simple_workflow, structured_workflow,
)
from gerbera_harness.tools.sources import LocalToolSource


class UnusedModel:
    async def complete(self, request):
        raise AssertionError("This workflow must not call a model")


@dataclass
class EchoNode:
    async def execute(self, state, context):
        return NodeResult(outcome="done", output={"message": context.input["prompt"]})


def echo_workflow(node=None):
    return (
        WorkflowBuilder("echo")
        .add_node("echo", node or EchoNode(), NodeDefinition(
            type="custom", inputs={"prompt": "/input/prompt"}, outcomes=("done",),
        ))
        .add_transition(Transition.model_validate({
            "from": "__entry__", "outcome": "start", "to": "echo",
        }))
        .add_transition(Transition.model_validate({
            "from": "echo", "outcome": "done", "to": "__exit__",
            "terminal": {"status": "succeeded", "output": {
                "message": "/nodes/echo/output/message",
            }},
        }))
        .build()
    )


def make_harness(workflow):
    return HarnessBuilder(HarnessServices(UnusedModel(), LocalToolSource())).with_workflow(workflow).build()


def test_entry_and_exit_keep_private_state_out_of_result():
    request = RunRequest(workflow="echo", input={"prompt": "hello"}, metadata={"secret": "private"})

    result = asyncio.run(make_harness(echo_workflow()).run(request))

    assert (result.status, result.current_node, result.output) == (
        RunStatus.SUCCEEDED, "__exit__", {"message": "hello"},
    )


def test_invalid_output_schema_exits_with_sanitized_error():
    compiled = echo_workflow()
    definition = compiled.definition.model_copy(update={"interface": WorkflowInterface(
        output_schema={"type": "object", "required": ["missing"]},
    )})
    from dataclasses import replace

    workflow = replace(compiled, definition=definition)
    result = asyncio.run(make_harness(workflow).run(RunRequest(workflow="echo", input={"prompt": "hello"})))

    assert result.error.code == "invalid_workflow_output"


def test_unknown_outcome_terminates_without_exposing_exception():
    class UnknownOutcome:
        async def execute(self, state, context):
            return NodeResult(outcome="unregistered")

    result = asyncio.run(make_harness(echo_workflow(UnknownOutcome())).run(
        RunRequest(workflow="echo", input={"prompt": "hello"}),
    ))

    assert (result.current_node, result.error.code) == ("__exit__", "invalid_node_outcome")


def test_exception_is_sanitized_at_exit():
    class BrokenNode:
        async def execute(self, state, context):
            raise RuntimeError("API_KEY=private")

    result = asyncio.run(make_harness(echo_workflow(BrokenNode())).run(
        RunRequest(workflow="echo", input={"prompt": "hello"}),
    ))

    assert "private" not in result.model_dump_json()


def test_background_run_cancellation_reaches_exit():
    async def scenario():
        started = asyncio.Event()

        class WaitingNode:
            async def execute(self, state, context):
                started.set()
                await asyncio.Event().wait()

        manager = RunManager(make_harness(echo_workflow(WaitingNode())))
        record = manager.start(RunRequest(workflow="echo", input={"prompt": "wait"}))
        await started.wait()
        manager.cancel(record.execution.state.run_id)
        await record.task
        return record.snapshot()

    result = asyncio.run(scenario())

    assert (result["status"], result["current_node"]) == ("cancelled", "__exit__")


def test_cancellation_before_task_entry_is_terminal():
    async def scenario():
        manager = RunManager(make_harness(echo_workflow()))
        record = manager.start(RunRequest(workflow="echo", input={"prompt": "wait"}))
        manager.cancel(record.execution.state.run_id)
        await manager.close()
        return record.snapshot()

    assert asyncio.run(scenario())["status"] == "cancelled"


def test_request_is_rejected_before_run_is_scheduled():
    workflow = simple_workflow()
    manager = RunManager(make_harness(workflow))

    with pytest.raises(ValueError, match="Schema validation"):
        manager.start(RunRequest(workflow="simple", input={"prompt": ""}))


def test_concurrent_runs_have_isolated_state_and_event_sequences():
    async def scenario():
        manager = RunManager(make_harness(echo_workflow()))
        first = manager.start(RunRequest(workflow="echo", input={"prompt": "one"}))
        second = manager.start(RunRequest(workflow="echo", input={"prompt": "two"}))
        await asyncio.gather(first.task, second.task)
        return (
            first.execution.result.output, second.execution.result.output,
            [event.id for event in first.events],
            len(first.events), len(second.events),
        )

    first, second, identifiers, first_count, second_count = asyncio.run(scenario())

    assert (first, second, identifiers) == (
        {"message": "one"}, {"message": "two"}, list(range(1, first_count + 1)),
    )


def test_both_presets_compile_and_allow_one_strategy_to_be_replaced():
    workflow = StructuredWorkflowBuilder().with_stage("plan", EchoNode()).build().compile()

    assert (simple_workflow().definition.name, structured_workflow().definition.name,
            isinstance(workflow.nodes["plan"], EchoNode)) == ("simple", "structured", True)


def test_loader_rejects_path_traversal(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    loader = WorkflowLoader(root, default_node_registry())

    with pytest.raises(ValueError, match="escapes"):
        loader.load(Path("../outside.json"))


def test_loader_rejects_symlink_escape(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (root / "link.json").symlink_to(outside)

    with pytest.raises(ValueError, match="escapes"):
        WorkflowLoader(root, default_node_registry()).load(Path("link.json"))


def test_loader_rejects_duplicate_json_keys(tmp_path: Path):
    path = tmp_path / "workflow.json"
    path.write_text('{"nodes": {}, "nodes": {}}')

    with pytest.raises(ValueError, match="Duplicate JSON key"):
        WorkflowLoader(tmp_path, default_node_registry()).load(Path(path.name))


def test_node_timeout_reaches_exit():
    async def scenario():
        class Waiting:
            async def execute(self, state, context):
                await asyncio.Event().wait()

        from dataclasses import replace

        compiled = echo_workflow(Waiting())
        node = compiled.definition.nodes["echo"].model_copy(update={
            "execution": ExecutionLimits(timeout_seconds=0.001),
        })
        workflow = replace(compiled, definition=compiled.definition.model_copy(update={"nodes": {"echo": node}}))
        return await make_harness(workflow).run(RunRequest(workflow="echo", input={"prompt": "wait"}))

    assert asyncio.run(scenario()).error.code == "node_timeout"
