import asyncio

import pytest

from gerbera_sdk.events.rules import OperatorEnum, RuleBuffer, RuleBus
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime


EVENT_KEY = ("STREAM", "board-1", "temperature")


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
        callback_script=(
            "async def callback(mcp_url, value):\n"
            "    return {'mcp_url': mcp_url, 'value': value}\n"
        ),
    )

    script_path = runtime.rules_path / f"{result['rule_id']}.py"
    assert result["script_path"] == str(script_path)
    assert script_path.exists()
    assert EVENT_KEY in rule_buffer.buffer
    assert asyncio.run(
        rule_bus.emit_evaluation_event(EVENT_KEY, 21)
    ) == {
        "mcp_url": "https://hardware.example.com/mcp",
        "value": 21,
    }


def test_agent_runtime_rejects_script_without_async_callback(
    tmp_path,
) -> None:
    rule_bus = RuleBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        rule_bus=rule_bus,
        rule_buffer=RuleBuffer(rule_bus),
        rules_path=tmp_path / ".gerbera" / "rules",
    )

    with pytest.raises(TypeError, match="must define async callback"):
        runtime.insert_rule(
            event_type=EVENT_KEY[0],
            microcontroller_id=EVENT_KEY[1],
            event_name=EVENT_KEY[2],
            expected_value=20,
            operator=OperatorEnum.GREATER_THAN,
            callback_script="def callback(mcp_url, value):\n    return value\n",
        )

    assert list(runtime.rules_path.iterdir()) == []
    assert rule_bus.rule_bus == {}
