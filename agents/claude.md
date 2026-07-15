# Gerbera Device Builder Guide

Use this when adding a new hardware component type.

## Brainstorming Mode

If the user is asking conceptual questions, comparing designs, or explicitly says
`brainstorm`, `do not implement`, `do not code`, or similar, do not edit files,
run implementation commands, scaffold code, or wire runtime behavior.

In brainstorming mode, respond with architecture, tradeoffs, examples, and
recommended next steps only. Wait for an explicit implementation request such as
`implement this`, `make the change`, `edit the files`, `scaffold it`, or
`do this` before modifying the repository.

## Mental Model

A `Connection` is a specific physical device wired to a microcontroller.

A firmware device builder is the code generator for that component type. The builder says:

- What Arduino libraries are needed.
- Which pins need `pinMode(...)`.
- Which MCP commands exist.
- What C++ handler code should be generated.
- Optionally, what setup lines, global definitions, streaming loop lines, and database schema are needed.

The `component_type` on `Connection` must match a key in `DEVICES_MAPPING`.

Example:

```python
Connection(
    id="green-led",
    name="green_led",
    component_type="led",
    pins={"out": "13"},
)
```

This uses:

```python
DEVICES_MAPPING["led"] = LEDFirmwareBuilder
```

## Required Files

For a new component called `foo`:

1. Add `src/gerbera_sdk/firmware/devices/foo.py`.
2. Implement `FooFirmwareBuilder(BaseFirmwareBuilder)`.
3. Register it in `src/gerbera_sdk/firmware/configurations.py`.
4. Add tests under `tests/test_foo_builder.py`.
5. If it should appear in an example system, add a `Connection` in `example_hardware_system.py`.

## Required Builder Methods

Every builder must implement:

```python
def required_libraries(self) -> list[LibrarySpec]:
    return []

def pin_modes(self, connection: Connection) -> list[PinModeSpec]:
    return []

def required_commands(self, connection: Connection) -> list[CommandSpec]:
    return [...]

def build_handler(self, connection: Connection) -> str:
    return "..."
```

Use optional hooks only when needed:

- `build_definitions(...)`: global C++ objects or variables, for example `Servo motor_servo;`.
- `build_setup_lines(...)`: setup code beyond `pinMode(...)`, for example `servo.attach(pin);`.
- `build_stream_lines(...)`: recurring loop code for database-backed streaming.
- `required_schema(...)`: database columns for streamed data.
- `output_contract(...)`: emitted MCP/STREAM fields and types.

## Serial Response Contract

Firmware responses that should return to MCP tools must use:

```text
MCP,<component_type>_<short_microcontroller_hash>,key:value
```

Example:

```cpp
Serial.println("MCP,led_8e910dfb,state:on");
```

Streaming data that should go to the event/database path must use:

```text
STREAM,<component_type>_<short_microcontroller_hash>,key:value,key:value
```

Example:

```cpp
Serial.println("STREAM,hw201_8e910dfb,value:1");
```

Do not return plain `state:on`, `value:1`, or `error:...` from generated handlers if MCP needs to read the result. The listener will ignore those because they do not include an event type and event name.

Use `connection.event_name` in builders so event/table names stay stable and stay under PostgreSQL's 63-byte identifier limit. For real hardware, the `microcontroller_id` should come from the UUID in `config.json["devices"]`; Gerbera hashes that board identity into a short deterministic suffix.

## Command Contract

Use `CommandSpec` and `ParameterSpec` to describe what the generated MCP tool accepts.

Example for a write-only device:

```python
CommandSpec(
    method="WRITE",
    description="Set the LED state.",
    params={
        "state": ParameterSpec(
            type=ParameterType.STRING,
            required=True,
            enum=["on", "off"],
            description="Desired LED state.",
        ),
    },
)
```

Use `enum` for constrained strings like `on/off`.

Use `min` and `max` for numeric values like motor speed or servo angle.

## Pin Contract

Only define pin modes when the firmware should call `pinMode(...)`.

Examples:

- LED output pin: `OUTPUT`
- Digital sensor output pin: `INPUT`
- Servo signal pin: usually no `pinMode`; `Servo.attach(...)` handles it.

Use pin names that match the builder code:

- LED: `{"out": "13"}`
- HW201: `{"out": "7"}`
- SG90/MG996R: `{"signal": "10"}`
- DC motor: `{"in1": "5", "in2": "6", "enable": "9"}`

## Database-backed Streaming

Only generate streaming behavior when the `Connection` has a `database`.

For database-compatible sensors:

1. Keep the normal request/response handler working.
2. Add separate streaming definitions/lines only when database is connected.
3. Implement `required_schema(...)` with `ColumnSpec`.
4. Implement `output_contract(...)` for `MCP` and `STREAM` fields.
5. Ensure stream payload keys match database column names.

For auto-generated columns:

- `id`: primary key / auto increment
- `created_at`: supplied by the runtime/event path

The firmware should usually emit only measured values, for example `value:1`. Do not rely on a database `CURRENT_TIMESTAMP` default for streamed event timing.

## Output Contract

If a device emits structured MCP or STREAM values, define them in `output_contract(...)`.

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
            description="Continuously streamed sensor value.",
        ),
    },
}
```

This contract is the source of truth for:

- device-emitted MCP fields
- device-emitted STREAM fields
- rule field validation
- buffer initialization

## New Device Checklist

- The component has a unique `component_type`.
- `DEVICES_MAPPING` contains the new type.
- All required pins are documented in tests.
- `required_commands(...)` matches the handler parser.
- Handler uses `parameterValue(input, "...")` for parameters.
- MCP responses use `MCP,<component_type>_<short_microcontroller_hash>,...`.
- Streaming responses use `STREAM,<component_type>_<short_microcontroller_hash>,...`.
- Output fields are declared in `output_contract(...)`.
- Any required library has both `include` and `install` in `LibrarySpec`.
- Tests assert command contract, pin modes, and generated handler strings.
