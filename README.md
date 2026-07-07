# gerbera-cli

Gerbera currently has two layers:

- `gerbera_cli`: local setup commands
- `gerbera_sdk`: hardware modeling and generated runtime contracts

## Current Goal

The current goal is simple:

- declare boards locally
- model hardware capabilities in Python
- generate a thin device-side command layer
- expose those capabilities cleanly to a higher runtime or MCP layer

## Boundaries

### `gerbera_cli`

The CLI is intentionally narrow.

Right now it is for:

- detecting and declaring boards
- installing Arduino libraries

It is not where hardware behavior is defined.

### `gerbera_sdk`

The SDK owns:

- the hardware model
- the command contract
- generated firmware/runtime building blocks

It is the source of truth for what a board can do.

## Core Decisions

### Hardware is declared, not inferred

Gerbera does not try to guess what is attached to a board.

The developer declares the hardware in code. That is more reliable and keeps the system predictable.

### `Connection` is the main unit

A `Connection` is not just a pin mapping. It represents one callable hardware capability.

Example:

```python
Connection(
    microcontroller_id=device_id,
    name="room_temperature",
    description="Temperature sensor on A0.",
    pins={"signal": "A0"},
    component_type="hw-201",
)
```

That single object is the thing that later becomes:

- a generated handler
- a command name
- a future MCP-facing capability

### Pins are named by role

Pins are modeled by semantic names, not position.

Example:

```python
pins={"signal": "A0"}
```

For multi-pin components:

```python
pins={"tx": "17", "rx": "16"}
```

This keeps generation explicit and avoids fragile ordering assumptions.

### Component type drives behavior

Each connection declares a `component_type`.

Example:

```python
component_type="hw-201"
```

That type maps to known behavior in configuration and code generation. The developer chooses the component type; the system does not invent one.

### The board command contract stays simple

The board should receive a small serial command string, not raw MCP JSON.

Examples:

```text
READ,room_temperature
WRITE,set_led,value:true
WRITE,set_motor,speed:120,direction:forward
```

This keeps the embedded side small and easy to parse.

### Parsing is shared infrastructure

Command parsing should be generated once and reused by all handlers.

The parser should produce:

- `action`
- `commandName`
- params

Handlers should receive structured parsed input instead of manually splitting strings themselves.

### Empty params are valid

Some commands, especially reads, do not need params.

Example:

```text
READ,room_temperature
```

That is a valid command.

### Reads are one-shot for MVP

For now, reads are one-shot requests, not streams.

That keeps the contract simpler and leaves streaming as a future extension.

### Firmware or device-side code should stay thin

The embedded layer should only:

- receive a command
- parse it
- route it
- touch hardware
- return a response

Business logic and orchestration stay on the Python side.

## Current Domain Model

The intended hierarchy is:

- `HardwareSystem`
  - many `Microcontroller`
- `Microcontroller`
  - many `Connection`

For MVP, `Microcontroller` should stay minimal:

```python
@dataclass
class Microcontroller:
    id: str
    port: str
    baud_rate: int
    fqbn: str
    description: str = ""
    connections: list[Connection] = field(default_factory=list)
```

## Current Flow

The current flow is:

1. Use the CLI to declare boards locally.
2. Build a `HardwareSystem` in Python.
3. Add `Microcontroller` objects.
4. Add `Connection` objects to each board.
5. Generate shared parser/routing code plus connection-specific handlers.
6. Use that generated layer as the bridge between Python and the device.

## `devices.json`

`devices.json` is the bridge from CLI setup to SDK modeling.

For now it should stay small and only hold board registry information, not component behavior.

## What Is Out of Scope Right Now

- automatic hardware detection
- streaming reads
- rich user-authored MCP schemas
- putting business logic on the board
- making the board understand MCP directly
- locking in a flashing workflow

## Run

CLI help:

```bash
PYTHONPATH=src python -m gerbera_cli.main --help
```

Tests:

```bash
PYTHONPATH=src .venv/bin/pytest
```
