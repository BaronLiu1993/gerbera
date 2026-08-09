import asyncio
from typing import Any

import pytest

from gerbera_sdk.events.reactions import (
    OperatorEnum,
        ReactionBus,
    ReactionTriggerModeEnum,
)
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
from gerbera_sdk.utils import hash_event_key


EVENT_KEY = ("STREAM", "board-1", "temperature")


def test_reaction_script_filename_is_the_event_key_hash(tmp_path) -> None:
    reaction_bus = ReactionBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        reaction_bus=reaction_bus,
        reaction_bus=reaction_bus,
        reactions_path=tmp_path,
    )

    script_path = runtime._reaction_script_path(EVENT_KEY)

    assert script_path.name == f"{hash_event_key(EVENT_KEY)}.py"


def test_agent_runtime_rejects_an_unregistered_event_key(tmp_path) -> None:
    reaction_bus = ReactionBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        reaction_bus=reaction_bus,
        reaction_bus=reaction_bus,
        reactions_path=tmp_path,
        valid_event_keys={EVENT_KEY},
    )

    with pytest.raises(ValueError, match="Event key is not registered"):
        runtime.insert_reaction(
            event_type="STREAM",
            microcontroller_id="board-1",
            event_name="invented",
            expected_value=1.0,
            operator=OperatorEnum.EQUAL,
            callback_body="return value",
        )

    assert list(tmp_path.glob("*.py")) == []


def test_agent_runtime_writes_and_registers_reaction_script(tmp_path) -> None:
    reaction_bus = ReactionBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        reaction_bus=reaction_bus,
        reaction_bus=reaction_bus,
        reactions_path=tmp_path / ".gerbera" / "reactions",
    )

    result = runtime.insert_reaction(
        event_type=EVENT_KEY[0],
        microcontroller_id=EVENT_KEY[1],
        event_name=EVENT_KEY[2],
        expected_value=20,
        operator=OperatorEnum.GREATER_THAN,
        callback_body=(
            "return {'mcp_url': mcp_url, 'value': value}\n"
        ),
        trigger_mode=ReactionTriggerModeEnum.ONCE,
    )

    script_path = runtime.reactions_path / f"{hash_event_key(EVENT_KEY)}.py"
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
    assert EVENT_KEY in reaction_bus.latest_values
    reaction = reaction_bus.get_reaction(EVENT_KEY)
    assert reaction is not None
    assert reaction.condition.expected == 20.0
    assert type(reaction.condition.expected) is float
    assert reaction.trigger_mode == ReactionTriggerModeEnum.ONCE
    assert asyncio.run(
        reaction_bus.emit_evaluation_event(EVENT_KEY, 21.0)
    ) == {
        "mcp_url": "https://hardware.example.com/mcp",
        "value": 21.0,
    }


@pytest.mark.parametrize(
    "expected_value",
    ["on", True, False, float("inf"), float("nan")],
)
def test_agent_runtime_rejects_non_finite_expected_before_writing_script(
    tmp_path,
    expected_value: Any,
) -> None:
    reaction_bus = ReactionBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        reaction_bus=reaction_bus,
        reaction_bus=reaction_bus,
        reactions_path=tmp_path / ".gerbera" / "reactions",
    )

    with pytest.raises(ValueError, match="finite numbers"):
        runtime.insert_reaction(
            event_type=EVENT_KEY[0],
            microcontroller_id=EVENT_KEY[1],
            event_name=EVENT_KEY[2],
            expected_value=expected_value,
            operator=OperatorEnum.EQUAL,
            callback_body="return value",
        )

    assert not runtime.reactions_path.exists()
    assert reaction_bus.reaction_bus == {}


def test_agent_runtime_rejects_complete_callback_function(
    tmp_path,
) -> None:
    reaction_bus = ReactionBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        reaction_bus=reaction_bus,
        reaction_bus=reaction_bus,
        reactions_path=tmp_path / ".gerbera" / "reactions",
    )

    with pytest.raises(ValueError, match="cannot define functions"):
        runtime.insert_reaction(
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

    assert not runtime.reactions_path.exists()
    assert reaction_bus.reaction_bus == {}


def test_agent_runtime_deletes_reaction_and_local_script(tmp_path) -> None:
    reaction_bus = ReactionBus()
    runtime = AgentRuntime(
        mcp_url="https://hardware.example.com/mcp",
        reaction_bus=reaction_bus,
        reaction_bus=reaction_bus,
        reactions_path=tmp_path / ".gerbera" / "reactions",
    )
    created = runtime.insert_reaction(
        event_type=EVENT_KEY[0],
        microcontroller_id=EVENT_KEY[1],
        event_name=EVENT_KEY[2],
        expected_value=20.0,
        operator=OperatorEnum.GREATER_THAN,
        callback_body="return None",
    )

    deleted = runtime.delete_reaction(
        event_type=EVENT_KEY[0],
        microcontroller_id=EVENT_KEY[1],
        event_name=EVENT_KEY[2],
    )

    assert deleted == created
    assert reaction_bus.get_reaction(EVENT_KEY) is None
    assert EVENT_KEY not in reaction_bus.latest_values
    assert not (
        runtime.reactions_path / f"{hash_event_key(EVENT_KEY)}.py"
    ).exists()
