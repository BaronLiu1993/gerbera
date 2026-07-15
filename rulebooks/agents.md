# Agent Instructions For Adding Gerbera Devices

Follow this exactly when implementing a new device builder.

## Brainstorming Mode

If the user is asking conceptual questions, comparing designs, or explicitly says
`brainstorm`, `do not implement`, `do not code`, or similar, do not edit files,
run implementation commands, scaffold code, or wire runtime behavior.

In brainstorming mode, respond with architecture, tradeoffs, examples, and
recommended next steps only. Wait for an explicit implementation request such as
`implement this`, `make the change`, `edit the files`, `scaffold it`, or
`do this` before modifying the repository.

## Do Not Guess The Contract

Before editing, inspect:

- `src/gerbera_sdk/firmware/devices/base.py`
- `src/gerbera_sdk/firmware/configurations.py`
- A similar existing device builder
- Existing tests for device builders

The source of truth is the current code, not memory.

## Implementation Steps

1. Create or edit one builder in `src/gerbera_sdk/firmware/devices/`.
2. Register the builder in `DEVICES_MAPPING`.
3. Add or update tests for the builder.
4. Run focused tests before reporting success.

Do not modify unrelated architecture while adding a component.

## Builder Shape

Every builder must extend `BaseFirmwareBuilder`.

Required methods:

```python
required_libraries(self) -> list[LibrarySpec]
pin_modes(self, connection: Connection) -> list[PinModeSpec]
required_commands(self, connection: Connection) -> list[CommandSpec]
build_handler(self, connection: Connection) -> str
```

Optional methods:

```python
build_definitions(self, connection: Connection) -> str
build_setup_lines(self, connection: Connection) -> list[str]
build_stream_lines(self, connection: Connection) -> list[str]
required_schema(self, connection: Connection) -> dict[str, ColumnSpec]
output_contract(
    self,
    connection: Connection,
) -> dict[OutputEventType, dict[str, OutputFieldSpec]]
```

Use optional methods only when the component actually needs them.

## Event Naming Rule

The event name is normally:

```text
<component_type>_<short_microcontroller_hash>
```

Generated firmware must use the same value.

Correct:

```python
f"MCP,{connection.event_name},state:on"
```

Wrong:

```python
f"MCP,{connection.name},state:on"
```

The runtime event bus registers by `connection.event_name`, not only by `connection.name`.
For real hardware, `microcontroller_id` should be the stable UUID from `config.json["devices"]`.
Gerbera hashes that UUID into a short deterministic suffix so event and table names stay short and stable.

## MCP Response Rule

Every one-off tool response must emit:

```text
MCP,<event_name>,key:value
```

Examples:

```cpp
Serial.println("MCP,led_8e910dfb,state:on");
Serial.println("MCP,dcmotor_8e910dfb,status:forward");
Serial.print("MCP,sg90_8e910dfb,angle:");
Serial.println(angle);
```

Do not emit plain responses for MCP tools.

Bad:

```cpp
Serial.println("state:on");
Serial.println("error:invalid_arg");
```

Good:

```cpp
Serial.println("MCP,led_8e910dfb,state:on");
Serial.println("MCP,led_8e910dfb,error:invalid_arg");
```

## Streaming Rule

Streaming responses must emit:

```text
STREAM,<event_name>,key:value
```

Only add streaming when the connection has a database path and the component needs continuous data capture.

Keep request/response code separate from streaming code. Do not break the normal handler when adding streaming.

## Parameters

Use `ParameterSpec`.

Constrained string:

```python
ParameterSpec(
    type=ParameterType.STRING,
    required=True,
    enum=["on", "off"],
)
```

Bounded number:

```python
ParameterSpec(
    type=ParameterType.INT,
    required=False,
    min=0,
    max=255,
)
```

Generated C++ should read params with:

```cpp
String value = parameterValue(input, "state");
```

## Pins

Use `PinModeSpec` for pins that need `pinMode(...)`.

```python
PinModeSpec(pin=connection.pins["out"], mode=PinMode.OUTPUT)
```

Do not add `pinMode(...)` for libraries that own setup through another API, such as `Servo.attach(...)`, unless the library or board specifically requires it.

## Libraries

If a device needs an Arduino library, return `LibrarySpec`.

```python
LibrarySpec(
    include="Servo.h",
    install="Servo",
)
```

The include is used in generated firmware. The install name is used by setup/install dependency code.

## Output Contract

If a device emits structured MCP or STREAM responses, define `output_contract(...)`.

Use `OutputEventType`, `OutputFieldType`, and `OutputFieldSpec`, not raw dictionaries of ad hoc strings.

Example:

```python
return {
    OutputEventType.MCP: {
        "value": OutputFieldSpec(
            type=OutputFieldType.INTEGER,
            description="Current digital sensor value.",
        ),
    },
    OutputEventType.STREAM: {
        "value": OutputFieldSpec(
            type=OutputFieldType.INTEGER,
            description="Continuously streamed digital sensor value.",
        ),
    },
}
```

Use this contract as the source of truth for:

- MCP response fields
- STREAM payload fields
- rule-authoring field validation
- buffer initialization

## Database Schema

If the device streams to a database, define `required_schema(...)`.

Use `ColumnSpec`, not raw dictionaries.

```python
return {
    "id": ColumnSpec(
        type=ColumnType.INTEGER,
        primary_key=True,
        nullable=False,
        sql_suffix="GENERATED BY DEFAULT AS IDENTITY",
    ),
    "value": ColumnSpec(
        type=ColumnType.INTEGER,
        nullable=False,
        idx=True,
    ),
    "created_at": ColumnSpec(
        type=ColumnType.TIMESTAMP,
        nullable=False,
    ),
}
```

Firmware stream payloads should contain only columns that are supplied by firmware.

Do not require firmware to emit `id`; the database should generate it.

`created_at` is emitted by the runtime/event path now, not by a database default. Keep the database column present, but do not rely on `CURRENT_TIMESTAMP` defaults for streamed event timing.

## Tests Required

For each new builder, test:

- Required command method and params
- Pin modes
- Required libraries
- Handler contains expected pin writes/reads
- Handler emits `MCP,<component_type>_<short_microcontroller_hash>,...`
- Streaming output emits `STREAM,<component_type>_<short_microcontroller_hash>,...` if applicable
- Output contract if the device emits MCP and/or STREAM fields
- Schema if database streaming is supported

Run focused tests:

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_<device>_builder.py -q
```

If server tool registration changes, also run:

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_mcp_server.py -q
```
