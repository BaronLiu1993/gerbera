import asyncio
import json
from types import SimpleNamespace

from gerbera_sdk.harness.agent.experiments.states.subloops.initialisation_loop import (
    CHEAP_RESEARCH_MODELS,
    InitialisationLoop,
    InitialisationLoopState,
)
from gerbera_sdk.harness.agent.model.model import ModelProviderEnum


class FakeHardwareClient:
    async def list_tools(self) -> list:
        return [
            SimpleNamespace(
                name="read_temperature",
                description="Read the temperature sensor",
                inputSchema={"type": "object"},
            )
        ]


class FakeModelClient:
    def send(self, messages, system_prompt, valid_schema) -> str:
        assert "hardware_tools" in messages[0]["content"]
        assert json.loads(messages[1]["content"])["url"] == "https://example.com"
        return json.dumps(
            {
                "complete": True,
                "summary": "The hardware and method are understood.",
            }
        )


def test_initialisation_loop_inspects_hardware_before_research(
    monkeypatch,
) -> None:
    loop = InitialisationLoop("key", ModelProviderEnum.OPENAI)
    monkeypatch.setattr(loop, "fetch_url", lambda url: "methodology")
    monkeypatch.setattr(
        "gerbera_sdk.harness.agent.model.model.Model.get_agent_client",
        lambda self: FakeModelClient(),
    )

    result = asyncio.run(
        loop.run(FakeHardwareClient(), ["https://example.com"])
    )

    assert result.complete
    assert loop.state is InitialisationLoopState.COMPLETE
    assert CHEAP_RESEARCH_MODELS[ModelProviderEnum.OPENAI] == "gpt-5-nano"
