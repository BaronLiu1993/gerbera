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
from gerbera_sdk.rule_engine import (
    OperatorEnum,
    Rule,
    RuleBus,
    RuleCallback,
    RuleCondition,
)

event_key = ("STREAM", "board-1", "temperature")
rule_bus = RuleBus()

rule = Rule(
    condition=RuleCondition(
        expected=30,
        operator=OperatorEnum.GREATER_THAN,
    ),
    callback=RuleCallback(
        callback=lambda value: f"Temperature is high: {value}",
    ),
)

rule_bus.register_rule(
    event_type=event_key[0],
    microcontroller_id=event_key[1],
    event_name=event_key[2],
    rule=rule,
)
result = rule_bus.emit_evaluation_event(event_key, 32)
```

`result` contains the matching callback's return value:

```python
"Temperature is high: 32"
```

For the MVP, one rule can be registered for each event key. Registering a
second rule for the same key raises `ValueError`.

## Values and comparisons

Rule values are limited to:

```python
bool | int | float | str
```

Equality operators compare the original values. Numeric operators convert both
the actual and expected values to `float` before comparing them.

## Custom callbacks

Pass any trusted local callable:

```python
callback = RuleCallback(
    callback=lambda value: call_external_api(value),
)
```

The most recently received value is available as `callback.val`.

## Optional latest-value buffer

`RuleBus` can evaluate incoming values directly. Use `RuleBuffer` when the
latest value must also be retained for future stateful or cross-event rules:

```python
from gerbera_sdk.rule_engine import RuleBuffer

buffer = RuleBuffer(rule_bus)
buffer.register_event_in_buffer(*event_key)

result = buffer.update_buffer_value(*event_key, 32)
latest_value = buffer.read_buffer_value(*event_key)
```

Registering an event again does not overwrite its current value. Updates for
unregistered events are ignored, while explicitly reading one raises `KeyError`.

## Runtime ownership

Each `ServerRuntime` starts with one empty `RuleBus` and one connected
`RuleBuffer`. The runtime injects that buffer into `EventListener`.

Unregistered event keys are ignored. Rules and watched buffer keys can be added
to these shared runtime objects later.

## Current scope

- synchronous callbacks
- one condition per rule
- one rule per event key
- latest-value storage, not event history
- one callback result returned to the event publisher
- trusted local developer code

The package does not perform network or hardware I/O itself. Callback code may
perform any work the developer chooses.
