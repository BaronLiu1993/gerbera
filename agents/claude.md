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
    name="green_led",
    component_type="led",
    pins={"out": "13"},
    description="Green status LED",
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
3. Export it from `src/gerbera_sdk/firmware/devices/__init__.py`.
4. Register it in `src/gerbera_sdk/firmware/configurations.py`.
5. Add focused tests under `tests/unit/` and registration/generation coverage
   under `tests/integration/` when applicable.
6. If it should appear in the example system, add a `Connection` in `index.py`.

Use `src/gerbera_sdk/firmware/devices/` for new work. The similarly named
`src/gerbera_sdk/firmware/function/devices/` directory is legacy and is not the
active `DEVICES_MAPPING` source.

## Fast Device-Type Decision

Choose one shape before writing code:

| Hardware behavior | Commands | Typical hooks |
|---|---|---|
| Input sensor | `READ` | pin modes, handler, MCP output contract |
| Output actuator | `WRITE` | pin modes/library setup, handler, MCP output contract |
| Streaming sensor | `READ` plus conditional internal stream `WRITE` | definitions, stream lines, schema, MCP/STREAM output contract |

Start simple. Do not add database hooks, streaming state, or libraries unless
the hardware actually needs them.

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

### How commands become MCP tools

Tool names are generated from `CommandSpec` and `connection.name`:

- `READ` -> `read_<name>`
- `WRITE` -> `write_<name>`
- Physical actuator `WRITE state:on/off` -> `turn_on_<name>` and
  `turn_off_<name>` convenience tools

Database-backed input sensors are a special case. Their firmware may use
`WRITE state:on/off` internally to control continuous sampling, but users are
not writing to or powering the sensor. For these devices, the public tools must
be exactly:

```text
read_<name>
turn_on_<name>_stream
turn_off_<name>_stream
```

The runtime identifies this stream command when `connection.database` is set
and the command is `WRITE` with a `state` enum containing `on` and `off`. Keep
the internal action registered for firmware dispatch, but do not expose
`write_<sensor>`, `turn_on_<sensor>`, or `turn_off_<sensor>`.

Use this pattern:

```python
def required_commands(self, connection: Connection) -> list[CommandSpec]:
    commands = [
        CommandSpec(
            method="READ",
            description="Read the current sensor value.",
        )
    ]
    if connection.database is not None:
        commands.append(
            CommandSpec(
                method="WRITE",
                params={
                    "state": ParameterSpec(
                        type=ParameterType.STRING,
                        enum=["on", "off"],
                        description="Turn continuous sensor streaming on or off.",
                    )
                },
                description="Turn continuous sensor streaming on or off.",
            )
        )
    return commands
```

Always add a server-registration test asserting the complete tool-name set.

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

1. Set `supports_database = True`.
2. Keep the normal request/response `READ` handler working.
3. Add separate stream state and loop lines only when a database is connected.
4. Handle internal `WRITE state:on/off` without treating it as a physical
   sensor write.
5. Implement `required_schema(...)` with `ColumnSpec`.
6. Implement `output_contract(...)` for `MCP` and `STREAM` fields.
7. Ensure stream payload keys match database column names.

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
- `firmware/devices/__init__.py` exports the builder.
- `DEVICES_MAPPING` registers the exact `component_type`.
- MCP tests assert the exact public tool set, especially for streaming sensors.
- Focused validation includes:

```bash
PYTHONPATH=src .venv/bin/pytest tests/unit/test_<device>_builder.py -q
PYTHONPATH=src .venv/bin/pytest tests/integration/test_firmware_generation.py -q
PYTHONPATH=src .venv/bin/pytest tests/integration/test_server_runtime.py -q
```
