import asyncio
from typing import Any

import pytest

from gerbera_sdk.events.rules import OperatorEnum, RuleBuffer, RuleBus
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
from gerbera_sdk.utils import hash_event_key


EVENT_KEY = ("STREAM", "board-1", "temperature")


def test_rule_script_filename_is_the_event_key_hash(tmp_path) -> None:
    rule_bus = RuleBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=rule_bus,
        rule_buffer=RuleBuffer(rule_bus),
        rules_path=tmp_path,
    )

    script_path = runtime._rule_script_path(EVENT_KEY)

    assert script_path.name == f"{hash_event_key(EVENT_KEY)}.py"


def test_agent_runtime_rejects_an_unregistered_event_key(tmp_path) -> None:
    rule_bus = RuleBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=rule_bus,
        rule_buffer=RuleBuffer(rule_bus),
        rules_path=tmp_path,
        valid_event_keys={EVENT_KEY},
    )

    with pytest.raises(ValueError, match="Event key is not registered"):
        runtime.insert_rule(
            event_type="STREAM",
            microcontroller_id="board-1",
            event_name="invented",
            expected_value=1.0,
            operator=OperatorEnum.EQUAL,
            callback_body="return value",
        )

    assert list(tmp_path.glob("*.py")) == []


def test_agent_runtime_writes_and_registers_rule_script(tmp_path) -> None:
    rule_bus = RuleBus()
    rule_buffer = RuleBuffer(rule_bus)
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=rule_bus,
        rule_buffer=rule_buffer,
        rules_path=tmp_path / ".gerbera" / "rules",
    )

    result = runtime.insert_rule(
        event_type=EVENT_KEY[0],
        microcontroller_id=EVENT_KEY[1],
        event_name=EVENT_KEY[2],
        expected_value=20,
        operator=OperatorEnum.GREATER_THAN,
        callback_body=(
            "return {'mcp_url': mcp_url, 'value': value}\n"
        ),
    )

    script_path = runtime.rules_path / f"{hash_event_key(EVENT_KEY)}.py"
    assert result["script_path"] == str(script_path)
    assert script_path.exists()
    assert script_path.read_text() == (
        "import httpx\n"
        "from fastmcp import Client\n"
        "\n"
        "\n"
        "async def callback(mcp_url, value):\n"
        "    return {'mcp_url': mcp_url, 'value': value}\n"
    )
    assert EVENT_KEY in rule_buffer.buffer
    rule = rule_bus.get_rule(EVENT_KEY)
    assert rule is not None
    assert rule.condition.expected == 20.0
    assert type(rule.condition.expected) is float
    assert asyncio.run(
        rule_bus.emit_evaluation_event(EVENT_KEY, 21.0)
    ) == {
        "mcp_url": "https://hardware.example.com/mcp",
        "value": 21.0,
    }


@pytest.mark.parametrize("expected_value", ["on", float("inf"), float("nan")])
def test_agent_runtime_rejects_non_finite_expected_before_writing_script(
    tmp_path,
    expected_value: Any,
) -> None:
    rule_bus = RuleBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=rule_bus,
        rule_buffer=RuleBuffer(rule_bus),
        rules_path=tmp_path / ".gerbera" / "rules",
    )

    with pytest.raises(ValueError, match="finite numbers"):
        runtime.insert_rule(
            event_type=EVENT_KEY[0],
            microcontroller_id=EVENT_KEY[1],
            event_name=EVENT_KEY[2],
            expected_value=expected_value,
            operator=OperatorEnum.EQUAL,
            callback_body="return value",
        )

    assert not runtime.rules_path.exists()
    assert rule_bus.rule_bus == {}


def test_agent_runtime_rejects_complete_callback_function(
    tmp_path,
) -> None:
    rule_bus = RuleBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=rule_bus,
        rule_buffer=RuleBuffer(rule_bus),
        rules_path=tmp_path / ".gerbera" / "rules",
    )

    with pytest.raises(ValueError, match="cannot define functions"):
        runtime.insert_rule(
            event_type=EVENT_KEY[0],
            microcontroller_id=EVENT_KEY[1],
            event_name=EVENT_KEY[2],
            expected_value=20.0,
            operator=OperatorEnum.GREATER_THAN,
            callback_body=(
                "def callback(mcp_url, value):\n"
                "    return value\n"
            ),
        )

    assert not runtime.rules_path.exists()
    assert rule_bus.rule_bus == {}


@pytest.mark.parametrize("mcp_url", ["", "not-a-url", "stdio"])
def test_agent_runtime_requires_configured_mcp_url(
    tmp_path,
    mcp_url: str,
) -> None:
    rule_bus = RuleBus()
    runtime = AgentRuntime(
        mcp_url=mcp_url,
        rule_bus=rule_bus,
        rule_buffer=RuleBuffer(rule_bus),
        rules_path=tmp_path / ".gerbera" / "rules",
    )

    with pytest.raises(RuntimeError, match="configured HTTP\\(S\\) MCP URL"):
        runtime.insert_rule(
            event_type=EVENT_KEY[0],
            microcontroller_id=EVENT_KEY[1],
            event_name=EVENT_KEY[2],
            expected_value=20.0,
            operator=OperatorEnum.GREATER_THAN,
            callback_body="return value",
        )

    assert not runtime.rules_path.exists()
    assert rule_bus.rule_bus == {}


def test_agent_runtime_deletes_rule_and_local_script(tmp_path) -> None:
    rule_bus = RuleBus()
    rule_buffer = RuleBuffer(rule_bus)
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=rule_bus,
        rule_buffer=rule_buffer,
        rules_path=tmp_path / ".gerbera" / "rules",
    )
    created = runtime.insert_rule(
        event_type=EVENT_KEY[0],
        microcontroller_id=EVENT_KEY[1],
        event_name=EVENT_KEY[2],
        expected_value=20.0,
        operator=OperatorEnum.GREATER_THAN,
        callback_body="return None",
    )

    deleted = runtime.delete_rule(
        event_type=EVENT_KEY[0],
        microcontroller_id=EVENT_KEY[1],
        event_name=EVENT_KEY[2],
    )

    assert deleted == created
    assert rule_bus.get_rule(EVENT_KEY) is None
    assert EVENT_KEY not in rule_buffer.buffer
    assert not (
        runtime.rules_path / f"{hash_event_key(EVENT_KEY)}.py"
    ).exists()
