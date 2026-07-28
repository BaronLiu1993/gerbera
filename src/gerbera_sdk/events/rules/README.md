# Rule Engine

The rule engine evaluates hardware event values and runs developer-defined
callbacks.

It is intentionally independent from serial transport, MCP, databases, and the
agent runtime. Those systems publish values into the rule engine.

## Event flow

```text
event value
→ RuleBus finds the rule registered for the EventKey
→ RuleCondition evaluates the value
→ the RuleCallback runs when the condition matches
→ the callback result is returned to the publisher
```

An `EventKey` is:

```python
(event_type, microcontroller_id, event_name)
```

## Basic usage

```python
import asyncio

from gerbera_sdk.events.rules import (
    OperatorEnum,
    Rule,
    RuleBus,
    RuleCallback,
    RuleCondition,
)

event_key = ("STREAM", "board-1", "temperature")
rule_bus = RuleBus()


async def report_high_temperature(mcp_url, value):
    return f"Temperature is high: {value}"


rule = Rule(
    condition=RuleCondition(
        expected=30,
        operator=OperatorEnum.GREATER_THAN,
    ),
    callback=RuleCallback(
        callback=report_high_temperature,
        mcp_url="https://hardware.example.com/mcp",
    ),
)

rule_bus.register_rule(
    event_type=event_key[0],
    microcontroller_id=event_key[1],
    event_name=event_key[2],
    rule=rule,
)
result = asyncio.run(
    rule_bus.emit_evaluation_event(event_key, 32)
)
```

`result` contains the matching callback's return value:

```python
"Temperature is high: 32"
```

For the MVP, one rule can be registered for each event key. Registering a
second rule for the same key raises `ValueError`.

## Values and comparisons

Rule values are finite floating-point numbers:

```python
float
```

When an event reaches the rule buffer, its single watched value is validated
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


callback = RuleCallback(
    callback=fetch_external_data,
    mcp_url="https://hardware.example.com/mcp",
)
```

The callback receives `mcp_url` and the triggering value. The most recently
received value is also available as `callback.val`.

### Calling an MCP tool from the script

The script can implement its MCP behavior directly:

```python
from gerbera_sdk.events.rules import RuleCallback
from gerbera_sdk.harness.agent.model.mcp_client import MCPClient


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


callback = RuleCallback(
    mcp_url="https://hardware.example.com/mcp",
    callback=turn_off_motor,
)
```

The generated script controls which tool to call, how to build arguments, and
what result to return.

## Optional latest-value buffer

`RuleBus` can evaluate incoming values directly. Use `RuleBuffer` when the
latest value must also be retained for future stateful or cross-event rules:

```python
from gerbera_sdk.events.rules import RuleBuffer

buffer = RuleBuffer(rule_bus)
buffer.register_event_in_buffer(*event_key)

result = asyncio.run(
    buffer.update_buffer_value(*event_key, {"value": 32})
)
```

Registering an event again does not overwrite its current value. Updates for
unregistered events are ignored.

## Runtime ownership

Each `ServerRuntime` starts with one empty `RuleBus` and one connected
`RuleBuffer`. The runtime injects that buffer into `EventListener`.

`GerberaRuntime` also registers an `insert_rule` MCP tool. Agents can pass the
event key, condition, operator, and Python callback body to this tool. The
runtime places that body inside:

```python
async def callback(mcp_url, value):
    return value
```

The tool hashes the three-part event key with SHA-256, stores the source under
`.gerbera/rules/<event-key-hash>.py`, loads the callback, and registers the rule
against the same live bus and buffer.

The callback source is transported as text, not as a file upload. A plan places
the Python source in a JSON string, the MCP client sends that string as the
`callback_body` argument, and `AgentRuntime.insert_rule` validates and places
it inside a fixed `async def callback(mcp_url, value):` template. Generated
scripts always import `httpx` and `Client` from `fastmcp`. The configured MCP
URL and normalized finite-float sensor value are injected when the callback
runs.
The completed source is then written into the runtime's local
`.gerbera/rules/` directory. This keeps imports, function signature, and
filesystem ownership under runtime control and does not require the model to
know or access a local path.

The `delete_rule` MCP tool accepts the same three-part event key. It unregisters
the rule and removes its generated callback file. Workflow-scoped rule actions
use it for cleanup after execution.

Agents can call `list_rule_events` first to retrieve the registered event keys
as a nested `event_type → microcontroller_id → event_name` dictionary. Each
event entry includes the connection name, component type, description, and
whether it is streamable.

Unregistered event keys are ignored. Rules and watched buffer keys can be added
to these shared runtime objects later.

The listener submits rule evaluation to a dedicated executor. Serial listener
threads continue reading hardware events while async callbacks wait for I/O.

## Current scope

- async callbacks
- one condition per rule
- one rule per event key
- latest-value storage, not event history
- one callback result returned to the event publisher
- trusted local developer code

The package does not perform network or hardware I/O itself. Callback code may
perform any work the developer chooses.
