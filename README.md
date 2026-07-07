# gerbera-cli

Gerbera has two layers:

- `gerbera_cli`: local setup commands for declaring boards and installing Arduino libraries
- `gerbera_sdk`: the modeling, firmware generation, transport, and MCP adapter layer

## Run

CLI help:

```bash
PYTHONPATH=src python -m gerbera_cli.main --help
```

Tests:

```bash
PYTHONPATH=src .venv/bin/pytest
```

## Project Structure

```text
src/
  gerbera_cli/
    commands/
      declare_devices_command.py
      install_library_command.py
    config.py
    main.py
  gerbera_sdk/
    components/
      component_schema_profiles.json
      registry.py
    firmware/
      builders/
      flasher.py
      generator.py
    hardware/
      connections.py
      hardware_system.py
      microcontroller.py
      pin_factory.py
    mcp/
      server.py
      transport_pool.py
    transport/
      runtime.py
      serial_connection.py
devices.json
tests/
```

## End-to-End Flow

This is the current flow from board detection to MCP tool execution.

### 1. Declare physical boards with the CLI

Run:

```bash
PYTHONPATH=src python -m gerbera_cli.main devices select
```

What happens:

- `gerbera_cli.main` registers the `devices` command group
- `declare_devices_command.py` runs `arduino-cli board list --format json`
- the CLI filters candidate ports and lets you select them interactively
- the selected boards are written to `devices.json`

`devices.json` is the bridge between the CLI and the SDK. It stores board IDs plus transport metadata such as:

- `port`
- `protocol`
- `protocol_label`
- `hwid`

Example:

```json
{
  "27b30005-ff68-4c81-93ec-8d3ce7c7a242": {
    "id": "27b30005-ff68-4c81-93ec-8d3ce7c7a242",
    "port": "/dev/cu.usbserial-1140",
    "protocol": "serial",
    "protocol_label": "Serial Port (USB)",
    "hwid": "USB VID:PID=0x1A86:0x7523"
  }
}
```

### 2. Model the hardware in Python

In the SDK, you create:

- a `Microcontroller` for each board in `devices.json`
- a `Connection` for each attached component you want Gerbera to expose
- a `HardwareSystem` as the top-level orchestration object

Example:

```python
from gerbera_sdk import Connection, HardwareSystem, Microcontroller

controller = Microcontroller(
    id="27b30005-ff68-4c81-93ec-8d3ce7c7a242",
    description="Kitchen controller",
    baud_rate=115200,
)

room_temperature = Connection(
    microcontroller_id=controller.id,
    name="room_temperature",
    description="Temperature sensor on A0.",
    pins={"signal": "A0"},
    component_type="hw-201",
)

controller.add_connection(room_temperature)

hardware_system = HardwareSystem(
    description="Kitchen sensors",
    microcontrollers=[controller],
)
```

What each object means:

- `Microcontroller`: one board plus its declared connections
- `Connection`: one callable hardware capability, identified by a command name like `room_temperature`
- `HardwareSystem`: orchestration over one or more boards

### 3. Validate the component against the component registry

When you add a `Connection`:

- `Microcontroller.add_connection()` checks the board exists in `devices.json`
- `ComponentRegistry` loads `components/component_schema_profiles.json`
- the registry validates that the declared `pins` match what that component type requires
- the microcontroller rejects duplicate connection names and duplicate pin usage on the same board

For example, the current `hw-201` profile declares:

- required pins: `signal`
- operation: `read`
- firmware template: `hw_201_read`
- output schema: `value`, `unit`

### 4. Derive MCP-facing schemas from the component profile

`Connection.to_dict()` calls `PinFactory.build(component_type)`.

That factory:

- loads the component profile
- converts `input` into `inputSchema`
- converts `output` into `outputSchema`
- only includes schemas that actually have properties

That means the component profile is the source of truth for both:

- firmware generation behavior
- MCP-visible tool schema

### 5. Generate Arduino firmware

Call:

```python
compiled = hardware_system.compile()
```

This returns one compiled artifact per microcontroller, including:

- generated firmware source
- sketch path on disk

Current actual flow:

- `HardwareSystem.compile()` iterates over microcontrollers
- `FirmwareGenerator.generate(microcontroller)` builds one sketch per board
- the generator chooses a builder from the component profile's `template`
- each builder contributes handler code for its component
- `FirmwareGenerator.write_sketch()` writes the result to `gerbera_firmware/<board_id>.ino`

The generated firmware contains:

- `setup()` with `Serial.begin(BAUD_RATE)`
- `loop()` that reads one line from serial
- command dispatch by `connection.name`
- handler functions like `handle_room_temperature()`

So the firmware contract is intentionally simple:

- host sends a string command over serial
- firmware parses the command name
- firmware executes the matching handler
- firmware prints a comma-separated response

### 6. Flash the generated sketch

Call:

```python
hardware_system.flash_microcontrollers(
    {"27b30005-ff68-4c81-93ec-8d3ce7c7a242": "<fqbn>"}
)
```

What happens:

- `Flasher.flash_microcontroller()` asks the board for its `port`
- `FirmwareGenerator.write_sketch()` ensures the sketch exists
- `arduino-cli compile --fqbn ...`
- `arduino-cli upload -p <port> --fqbn ...`

Gerbera does not infer `fqbn` yet. You pass it in explicitly.

### 7. Build runtime commands in the SDK

At runtime, the SDK does not open serial ports inside `ConnectionRuntime` anymore. It only handles command formatting and response parsing.

Current command flow:

- `HardwareSystem.build_read_command(microcontroller_id, connection_name)`
- delegates to `ConnectionRuntime.build_read_command(connection)`
- which currently returns the connection name for reads

Example read command:

```text
room_temperature
```

If parameters are needed later, `ConnectionRuntime.build_command()` supports:

```text
command_name,param_name:type:value,param_name:type:value
```

Example:

```text
set_led,value:bool:true,duration:int:5
```

### 8. Execute over persistent serial transport

Persistent serial connections live in the MCP transport layer, not in the pure runtime formatter.

Current flow:

- `SerialTransportPool` caches one `SerialConnection` per board ID
- `get_connection()` opens the serial port once using `port` from `devices.json` and `baud_rate` from `Microcontroller`
- `execute()` asks `HardwareSystem.prepare_command(...)` for the command payload
- it sends the command string over serial
- it parses the board's string response with `HardwareSystem.parse_response(...)`

The low-level serial class is intentionally thin:

- `connect(port, baud)`
- `send(command)`
- `destroy()`

### 9. Expose everything as MCP tools

`GerberaMCPServer` is the adapter from your modeled `HardwareSystem` into FastMCP.

Current MCP flow:

- `GerberaMCPServer.create_server()` creates one FastMCP server
- it builds one overview tool: `gerbera_hardware_overview`
- it builds one tool per `Connection`
- each tool name is the connection name, such as `room_temperature`
- each tool calls into `SerialTransportPool.execute(...)`

So the final chain is:

```text
LLM tool call
-> FastMCP tool
-> GerberaMCPServer
-> SerialTransportPool
-> HardwareSystem.prepare_command()
-> SerialConnection.send(...)
-> Arduino firmware handler
-> serial response
-> HardwareSystem.parse_response()
-> MCP tool result
```

## Mental Model

The simplest way to think about Gerbera right now is:

1. The CLI discovers boards and writes `devices.json`
2. The SDK models what is attached to those boards
3. The component registry defines what each component type means
4. The firmware generator turns that model into Arduino code
5. The flasher uploads that code
6. The runtime sends simple serial commands
7. The MCP layer turns those commands into tools an LLM can call

## Current Boundaries

The current code is easiest to follow if you read it by responsibility:

- `gerbera_cli/`: local setup commands
- `gerbera_sdk/components/`: component metadata and validation
- `gerbera_sdk/hardware/`: domain objects and orchestration
- `gerbera_sdk/firmware/`: sketch generation and flashing
- `gerbera_sdk/transport/`: command formatting and raw serial I/O
- `gerbera_sdk/mcp/`: MCP server and persistent transport adapter

## Current Limitations

- `devices.json` is still used directly by `Microcontroller.get_board_information()`
- only the `hw-201` component profile is implemented
- reads are the main supported operation right now
- flashing requires you to provide `fqbn`
- MCP is optional and requires the `fastmcp` dependency
