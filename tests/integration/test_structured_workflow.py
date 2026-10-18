import asyncio

from gerbera_harness.extensions.hardware import HardwareContextExtension
from gerbera_harness.runtime.contracts import HarnessServices
from gerbera_harness.runtime.harness import HarnessBuilder
from gerbera_harness.runtime.state_machine.schemas import RunRequest
from gerbera_harness.runtime.workflows.presets import structured_workflow
from gerbera_harness.tools.base import ToolSpec


class ScriptedModel:
    def __init__(self):
        self.responses = iter([
            {"tasks": ["Set LED"], "success_criteria": ["LED is on"]},
            {"message": "LED is off"},
            {"decision": "accepted", "message": "Sufficient evidence"},
            {"plan": "Set LED", "calls": [{"name": "set_led", "arguments_json": '{"on":true}'}]},
            {"decision": "approved", "message": "Valid command"},
            {"decision": "accepted", "message": "Fresh hardware snapshot verifies on"},
            {"decision": "succeeded", "message": "LED is on"},
        ])

    async def complete(self, request):
        return next(self.responses)


class RemoteTools:
    def __init__(self):
        self.calls = []
        self.on = False

    async def list_tools(self):
        return [
            ToolSpec("get_current_environment_state", "environment", {"type": "object"}, read_only=True),
            ToolSpec("get_current_hardware_state", "hardware", {"type": "object"}, read_only=True),
            ToolSpec("set_led", "LED", {
                "type": "object", "properties": {"on": {"type": "boolean"}}, "required": ["on"],
            }),
        ]

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == "set_led":
            self.on = arguments["on"]
        return {"on": self.on}


def test_structured_stages_review_before_and_after_execution():
    tools = RemoteTools()
    builder = HarnessBuilder(HarnessServices(ScriptedModel(), tools))
    builder.with_extension(HardwareContextExtension(tools))
    harness = builder.with_workflow(structured_workflow()).build()

    result = asyncio.run(harness.run(RunRequest(
        workflow="structured", input={"prompt": "Turn the LED on"},
    )))

    assert (result.status, result.steps, result.output, tools.calls) == (
        "succeeded", 8, {"message": "LED is on"},
        ["get_current_environment_state", "get_current_hardware_state", "set_led",
         "get_current_environment_state", "get_current_hardware_state"],
    )
