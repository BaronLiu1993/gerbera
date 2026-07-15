# Rule Engine

This folder owns deterministic rule evaluation for Gerbera hardware events.

READ: this is still an MVP design. The shape is now clear enough to document, but the implementation is still early and should be cleaned up.

## Purpose

The rule engine lets a user:

- define one or more `Condition`s against device output fields
- group those conditions into a `RuleGroup`
- attach the rule group to a `HardwareSystem`
- evaluate the rule group whenever one of the watched event sources updates

The current model is state-based, not history-based.

That means:

- rules evaluate against the latest value stored for a watched event
- the engine does not try to preserve every intermediate event for temporal analysis
- this is suitable for automation and threshold logic, not yet for precise stream-processing semantics

## Ownership

This folder owns:

- condition structure
- rule group structure
- rule buffer structure
- rule bus structure
- deterministic evaluation flow

This folder does not own:

- serial transport
- firmware generation
- MCP server registration
- database writes
- event parsing

Those are owned elsewhere and feed data into this layer.

## Core Data Structures

### `EventKey`

Defined in [events/utils.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/events/utils.py).

```python
EventKey = tuple[str, str, str]
```

It is:

```text
(event_type, microcontroller_id, event_name)
```

Example:

```text
("MCP", "27b30005-ff68-4c81-93ec-8d3ce7c7a242", "hw201_8e910dfb")
```

This identifies one event source.

### `Condition`

Defined in [condition.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/rule_engine/condition.py).

A condition is one comparison against one source field.

Current shape:

```python
Condition(
    event_type="MCP",
    microcontroller_id="...",
    event_name="...",
    field_name="value",
    expected="1",
    operator=OperatorEnum.EQUAL,
)
```

Important behavior:

- a condition targets exactly one `EventKey`
- `field_name` is the field inside that source payload
- `actual is None` evaluates to `False`
- numeric operators cast `actual` and `expected` to `float`

### `RuleGroup`

Defined in [rule_group.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/rule_engine/rule_group.py).

A rule group contains:

- `conditions: list[Condition]`
- `operator: AND | OR`
- `callback: Callable[[], None]`
- `rule_buffer`

The rule group evaluates all of its conditions against the shared rule buffer.

Current behavior:

- `AND`: all conditions must pass
- `OR`: at least one condition must pass
- if matched, the callback is invoked

### `RuleBuffer`

Defined in [rule_buffer.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/rule_engine/rule_buffer.py).

This is the in-memory latest-value store:

```python
buffer: dict[EventKey, dict[str, Any]]
```

Example:

```python
{
    ("MCP", "board-1", "hw201_8e910dfb"): {
        "value": "1",
    }
}
```

The rule buffer:

- pre-registers watched fields as `None`
- stores the latest known value for those fields
- emits a rule evaluation event after an update

Current runtime registration only seeds the field a rule actually watches, not the entire device output contract.

### `RuleBus`

Defined in [rule_bus.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/rule_engine/rule_bus.py).

This is the reverse index:

```python
dict[EventKey, list[RuleGroup]]
```

Meaning:

- when this source updates
- evaluate these rule groups

Example:

```python
{
    ("MCP", "board-1", "hw201_8e910dfb"): [rule_group_a, rule_group_b],
}
```

This is the key runtime optimization:

- one event source can fan out to many rule groups
- one rule group can appear under many source keys

## How Rule Registration Works

Rules are attached at the `HardwareSystem` layer.

Relevant file:

- [hardware_system.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/models/hardware_system.py)

The hardware system owns:

- `rule_groups`
- a shared `rule_bus`
- a shared `rule_buffer`

### Registration Process

When a `RuleGroup` is added:

1. `HardwareSystem.add_rule_groups(...)` is called
2. each rule group is prepared
3. the rule group is attached to the shared `rule_buffer`
4. each condition is inspected
5. the owning `Connection` is found by:
   - `microcontroller_id`
   - `event_name`
6. the condition is validated against the device builder's `output_contract(...)`
7. only the watched field is registered in the shared rule buffer
8. the condition's source key is registered on the rule bus

## How Conditions Are Created

Conditions should be created from `Connection`, not manually assembled by end users.

Relevant file:

- [connection.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/models/connection.py)

Use:

```python
connection.create_condition(
    field_name="value",
    operator="==",
    expected="1",
    event_type="MCP",
)
```

Why:

- the connection knows `microcontroller_id`
- the connection knows `event_name`
- the device builder knows which fields are valid through `output_contract(...)`

Current behavior:

- `event_type` is required
- the requested field must exist on that device's output contract for that event type
- invalid fields raise immediately

## Runtime Flow

### Registration-Time Flow

```mermaid
flowchart TD
    A[Connection.create_condition(...)] --> B[Condition]
    B --> C[RuleGroup]
    C --> D[HardwareSystem.add_rule_groups(...)]
    D --> E[Find owning Connection]
    E --> F[Validate against device output_contract]
    F --> G[Register watched field in RuleBuffer]
    F --> H[Register source key to RuleBus]
```

### Event-Time Flow

```mermaid
flowchart TD
    A[Event source updates] --> B[RuleBuffer.update_event_value(...)]
    B --> C[Store latest payload values]
    C --> D[RuleBus.emit_evaluation_event(...)]
    D --> E[Find RuleGroups for EventKey]
    E --> F[RuleGroup.evaluate_rule_group()]
    F --> G[Condition.evaluate_condition(...)]
    G --> H{Matched?}
    H -->|Yes| I[Callback()]
    H -->|No| J[No action]
```

## Relationship To Device Builders

The rule engine depends on device builders for field validation.

Source of truth:

- [base.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/firmware/devices/base.py)
- device builder implementations like [hw201.py](/Users/jiexuanliu/Desktop/firecracker/cli/src/gerbera_sdk/firmware/devices/hw201.py)

Every device may define:

```python
output_contract(...) -> dict[OutputEventType, dict[str, OutputFieldSpec]]
```

This contract tells the rule engine:

- which `MCP` fields are valid
- which `STREAM` fields are valid
- which fields can be used in a condition

## Current Constraints

The current MVP has several intentional limits:

- callbacks are `Callable[[], None]`
- callbacks are invoked immediately and synchronously
- evaluation is latest-value only
- no temporal windows
- no history buffer
- no deduplicated callback suppression
- no payload passed into callbacks yet

This is enough for deterministic threshold rules and simple automation.

## Current Expected Shapes

### Rule Bus

```python
{
    EventKey: [RuleGroup, RuleGroup, ...]
}
```

### Rule Buffer

```python
{
    EventKey: {
        "field_name": latest_value_or_none
    }
}
```

### Rule Group

```python
RuleGroup(
    conditions=[Condition(...), Condition(...)],
    operator=RuleGroupOperatorEnum.AND,
    callback=my_callback,
)
```

### Condition

```python
Condition(
    event_type="MCP",
    microcontroller_id="...",
    event_name="...",
    field_name="value",
    expected="1",
    operator=OperatorEnum.EQUAL,
)
```

## Future Work

These are the main next steps.

### 1. Pass payload into callbacks

Current callbacks are:

```python
Callable[[], None]
```

This is restrictive.

Likely next improvement:

```python
Callable[[dict[str, Any]], None]
```

Where the payload is built from the matched condition values.

### 2. Clean circular runtime ownership

Current ownership is workable but still a bit tangled:

- `HardwareSystem` owns `RuleBuffer`
- `RuleBuffer` owns `RuleBus`
- `RuleBus` references `RuleGroup`
- `RuleGroup` references `RuleBuffer`

This should likely be refactored into a clearer runtime orchestration object later.

### 3. Improve deduplication

Current dedupe for rule groups is based on `id`.

That is acceptable for now but weak as a semantic uniqueness rule.

### 4. Add tests

This folder needs focused tests for:

- condition creation from `Connection`
- invalid field rejection
- rule registration into `HardwareSystem`
- `AND` and `OR` evaluation
- `None` startup values
- one source mapping to many rule groups

### 5. Add richer callback payloads

Rules will eventually need to know:

- which condition matched
- what values were used
- maybe timestamps

### 6. Consider selective evaluation improvements

The current model is synchronous and event-driven.

That is fine for MVP, but later we may want:

- coalescing
- dirty-key processing
- deferred execution

Only do that if actual event volume justifies the complexity.

### 7. Add documentation examples

Once the API settles, add end-to-end examples showing:

- create a condition from a connection
- build a rule group
- attach it to a hardware system
- trigger a callback from an event update

## Summary

The current rule engine is:

- explicit
- device-contract validated
- latest-state based
- attached at the hardware-system runtime

It is not yet a general stream-processing engine, and that is intentional.
