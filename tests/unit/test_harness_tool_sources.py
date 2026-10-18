import asyncio

import pytest

from gerbera_harness.runtime.nodes.tools import ToolExecutionConfig, ToolExecutionNode
from gerbera_harness.runtime.contracts import HarnessServices, NodeContext
from gerbera_harness.runtime.state_machine.schemas import WorkflowState
from gerbera_harness.tools.base import ToolSpec
from gerbera_harness.tools.sources import CompositeToolSource


class RecordingSource:
    def __init__(self, name, read_only=True):
        self.name = name
        self.read_only = read_only
        self.calls = []

    async def list_tools(self):
        return [ToolSpec(self.name, "test", {"type": "object"}, read_only=self.read_only)]

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        return {"source": self.name}


def test_composite_routes_to_the_owning_source():
    first = RecordingSource("first")
    second = RecordingSource("second")

    result = asyncio.run(CompositeToolSource((first, second)).call_tool("second", {}))

    assert (result, first.calls, second.calls) == ({"source": "second"}, [], ["second"])


def test_composite_rejects_name_collisions():
    source = CompositeToolSource((RecordingSource("same"), RecordingSource("same")))

    with pytest.raises(ValueError, match="Duplicate tool"):
        asyncio.run(source.list_tools())


def test_read_only_node_validates_all_calls_before_side_effects():
    first = RecordingSource("inspect")
    second = RecordingSource("move", read_only=False)
    tools = CompositeToolSource((first, second))

    async def ignore(event):
        pass

    context = NodeContext(HarnessServices(object(), tools), ignore, input={
        "calls": [{"name": "inspect"}, {"name": "move"}],
    })
    node = ToolExecutionNode(ToolExecutionConfig(access="read_only"))

    with pytest.raises(PermissionError):
        asyncio.run(node.execute(WorkflowState(workflow="test", input={}), context))

    assert first.calls == []
