# Runtime

The runtime folder owns the live server process around the declared hardware graph.

It is responsible for:

- opening and closing serial connections
- registering MCP tools
- translating command specs into wire commands
- registering MCP and STREAM events
- starting and stopping listener threads
- coordinating stream flushing and database writes

It is not responsible for:

- defining the hardware graph itself
- device-specific firmware behavior
- pin modeling
- board/package metadata for compilation

## Files

```text
server.py               Thin facade over ServerRuntime.
server_runtime.py       Top-level runtime orchestrator.
board_runtime.py        Per-process board transport pool and lifecycle.
event_runtime.py        Event/listener runtime helper.
command_runtime.py      Command compilation and response parsing.
serial_connection.py    Raw serial transport wrapper.
commands.py             Compatibility shim for CommandCompiler import path.
```

## Ownership

`ServerRuntime` owns:

- startup and shutdown order
- MCP app/tool registration
- event registration
- binding executable actions onto connections
- command dispatch through board transport

`BoardRuntime` owns:

- opening one serial connection per microcontroller
- looking up the active serial connection for a board
- closing active serial connections

`EventRuntime` should own:

- event bus registration
- event listener lifecycle
- event runtime assembly

Right now, some of that logic still lives in `ServerRuntime`.

`CommandCompiler` owns:

- reading command specs from device builders
- validating and serializing command parameters
- parsing firmware response payloads
- building command descriptions for MCP tools

## Runtime Flow

```mermaid
flowchart TD
    A[HardwareSystem] --> B[ServerRuntime]
    B --> C[BoardRuntime.start]
    B --> D[Register MCP/STREAM events]
    B --> E[Register MCP tools]
    C --> F[SerialConnection]
    E --> G[CommandCompiler.build_command]
    G --> F
    F --> H[Firmware]
    H --> I[EventListener]
    I --> J[EventBus]
    J --> K[MCP response or stream buffer]
```

## Boundary Rule

The runtime layer should know how the system runs.

The hardware layer should only know what the system is.

If a class needs to start threads, open ports, register MCP tools, or configure the event worker, it belongs in runtime rather than hardware.
