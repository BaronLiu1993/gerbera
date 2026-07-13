# Server

The server folder owns the runtime MCP server, serial command execution, tool registration, and response waiting.

## Files

```text
server.py               GerberaServer runtime orchestration.
commands.py             CommandCompiler for command strings and response parsing.
serial_connection.py    Serial port wrapper.
```

## Ownership

This folder owns:

- registering MCP tools from connection command specs
- opening one serial connection per microcontroller
- sending command strings to firmware
- waiting for MCP event responses
- starting/stopping event listeners
- delegating stream lifecycle cleanup to `StreamController`

This folder does not own:

- device-specific firmware logic
- database schema design
- buffer internals
- stream event parsing

## Tool Call Flow

```mermaid
flowchart TD
    A[MCP tool] --> B[CommandCompiler.build_command]
    B --> C[SerialConnection.write or send]
    C --> D[Arduino firmware]
    D --> E[MCP serial event]
    E --> F[EventListener]
    F --> G[EventBus]
    G --> H[Event response queue]
    H --> I[GerberaServer returns dict]
```

## Stream Toggle Flow

```mermaid
flowchart TD
    A[turn_on_x_stream] --> B[WRITE state:on]
    B --> C[Arduino stream flag on]
    D[turn_off_x_stream] --> E[WRITE state:off]
    E --> F[Arduino stream flag off]
    F --> G[StreamController.stop_stream]
    G --> H[Flush partial stream buffer]
```

## Rule

`GerberaServer` should orchestrate. It should not know how buffers work internally.
