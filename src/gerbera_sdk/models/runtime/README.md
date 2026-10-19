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
server_runtime.py       MCP tools, events, listeners, and command dispatch.
board_runtime.py        Per-process board transport pool and lifecycle.
camera_runtime.py       Per-process camera transport, latest-frame cache, and lifecycle.
command_runtime.py      Command compilation and response parsing.
model_runtime.py        Model inference registration, output state, and lifecycle.
runtime_lifecycle.py    SDK-owned preparation, resource startup and cleanup.
storage.py              Stream schema preparation and bounded database startup wait.
readiness.py            Live dependency readiness reports.
```

## Ownership

`GerberaRuntime` owns:

- composing the SDK-owned preparation and lifecycle
- resolving the database and constructing one event worker for stream writes

`ServerRuntime` owns:

- MCP app/tool registration
- event registration
- building the nested runtime event catalog used by agents
- event listener health/tool exposure (lifecycle belongs to `RuntimeLifecycle`)
- binding executable actions onto connections
- command dispatch through board transport

`RuntimeLifecycle` owns storage preparation, firmware reconciliation and resource
startup/shutdown order. Every normal SDK server startup uses it, independently of
the CLI. Cleanup callbacks are registered before starting dependencies so partial
startup failures and interruptions release already-owned resources.

`RuntimeReadiness` checks lifecycle phase, board sessions/listeners, cameras,
inference failures and event-worker health. `/ready` returns 503 while unavailable
and 200 when ready; it is distinct from HTTP liveness. The CLI polls these reports
without reproducing SDK validation or examining device state itself.

`BoardRuntime` owns:

- opening one configured transport per microcontroller
- looking up the active transport for a board
- closing and reconnecting active transports

`CommandCompiler` owns:

- reading command specs from device builders
- validating and serializing command parameters
- parsing firmware response payloads
- building command descriptions for MCP tools

## Runtime Flow

```mermaid
flowchart TD
    A[HardwareSystem] --> B[GerberaRuntime]
    B --> C[BoardRuntime.start]
    B --> D[EventWorker.start]
    B --> E[ServerRuntime]
    E --> F[Register MCP/STREAM events and tools]
    E --> G[Start EventListener]
    C --> H[BoardTransport]
    F --> I[CommandCompiler.build_command]
    I --> H
    H --> J[Firmware]
    G --> K[EventBus]
    J --> G
    K --> L[MCP response or stream buffer]
    L --> D
    D --> M[Database]
```

## Boundary Reaction

The runtime layer should know how the system runs.

The hardware layer should only know what the system is.

If a class needs to start threads, open ports, register MCP tools, or configure the event worker, it belongs in runtime rather than hardware.
