# Reaction Engine

The reaction engine evaluates hardware event values and runs developer-defined
callbacks.

It is intentionally independent from serial transport, MCP, databases, and the
agent runtime. Those systems publish values into the reaction engine.

## Event flow

```text
event value
→ ReactionBus finds the reaction registered for the EventKey
→ ReactionCondition evaluates the value
→ the ReactionCallback runs when the condition matches
→ the callback result is returned to the publisher
```

An `EventKey` is:

```python
(event_type, microcontroller_id, event_name)
```

## Basic usage

```python
import asyncio

from gerbera_sdk.events.reactions import (
    OperatorEnum,
    Reaction,
    ReactionBus,
    ReactionCallback,
    ReactionCondition,
)

event_key = ("STREAM", "board-1", "temperature")
reaction_bus = ReactionBus()


async def report_high_temperature(mcp_url, value):
    return f"Temperature is high: {value}"


reaction = Reaction(
    condition=ReactionCondition(
        expected=30,
        operator=OperatorEnum.GREATER_THAN,
    ),
    callback=ReactionCallback(
        callback=report_high_temperature,
        mcp_url="https://hardware.example.com/mcp",
    ),
)

reaction_bus.register_reaction(
    event_type=event_key[0],
    microcontroller_id=event_key[1],
    event_name=event_key[2],
    reaction=reaction,
)
result = asyncio.run(
    reaction_bus.emit_evaluation_event(event_key, 32)
)
```

`result` contains the matching callback's return value:

```python
"Temperature is high: 32"
```

For the MVP, one reaction can be registered for each event key. Registering a
second reaction for the same key raises `ValueError`.

Each reaction has a trigger mode. `once` atomically claims the first matching event
and invokes the callback at most once per registration. `repeat` invokes the
callback for every matching event and preserves the original level-triggered
behavior.

## Values and comparisons

Reaction values are finite floating-point numbers:

```python
float
```

When an event reaches the reaction buffer, its single watched value is validated
and converted to `float`. Numeric strings and integers are accepted; text and
non-finite values are rejected. Conditions and callbacks therefore receive
only floats.

## Custom callbacks

Pass any trusted local async callable:

```python
async def fetch_external_data(mcp_url, value):
    response = await http_client.get(
        "https://example.com/data",
        params={"value": value},
    )
    return response.json()


callback = ReactionCallback(
    callback=fetch_external_data,
    mcp_url="https://hardware.example.com/mcp",
)
```

The callback receives `mcp_url` and the triggering value. The most recently
received value is also available as `callback.val`.

### Calling an MCP tool from the script

The script can implement its MCP behavior directly:

```python
from gerbera_sdk.events.reactions import ReactionCallback
from gerbera_harness.agent.model.mcp_client import MCPClient


async def turn_off_motor(mcp_url, value):
    async with MCPClient(mcp_url) as client:
        tools = await client.list_tools()
        allowed_tool_names = frozenset(tool.name for tool in tools)

        return await client.call_tool(
            "turn_off_motor",
            {
                "trigger_value": value,
            },
            allowed_tool_names,
        )


callback = ReactionCallback(
    mcp_url="https://hardware.example.com/mcp",
    callback=turn_off_motor,
)
```

The generated script controls which tool to call, how to build arguments, and
what result to return.

## Latest Values

`ReactionBus` owns registered reactions and their latest numeric values:

```python
result = asyncio.run(
    reaction_bus.update_reaction_value(*event_key, {"value": 32})
)
```

Updates for unregistered events are ignored.

## Runtime ownership

Each `ServerRuntime` starts with one empty `ReactionBus`. The runtime injects
that bus into `EventListener`.

Local reaction create/delete MCP tools are intentionally disabled while callback
execution moves to harness.

Agents can call `list_reaction_events` first to retrieve the registered event keys
as a nested `event_type → microcontroller_id → event_name` dictionary. Each
event entry includes the connection name, component type, description, and
whether it is streamable.

Unregistered event keys are ignored. Reactions and watched buffer keys can be added
to these shared runtime objects later.

The listener submits reaction evaluation to a dedicated executor. Serial listener
threads continue reading hardware events while async callbacks wait for I/O.

## Current scope

- async callbacks
- one condition per reaction
- one reaction per event key
- `once` and `repeat` trigger modes
- latest-value storage, not event history
- one callback result returned to the event publisher
- trusted local developer code

The package does not perform network or hardware I/O itself. Callback code may
perform any work the developer chooses.
