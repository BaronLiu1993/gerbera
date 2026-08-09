# Models

READ: we will need to clean up the code for this modelling. It is messy right now and does not fully reflect the intended user experience yet. THE SOURCE OF TRUTH FOR MICROCONTROLLERS IS `config.json["devices"]`.

The models folder owns the hardware declaration graph and the database connection used by the runtime.

Models should stay focused on:

- relationships
- identity
- validation
- database connection metadata

## Files

```text
hardware_system.py      Top-level hardware declaration.
microcontroller.py      Board identity resolved from config.json via port.
connection.py           One declared device connection on a board.
database.py             PostgreSQL connection details and insert execution.
pin.py                  Pin model support.
```

## Ownership

This folder owns:

- hardware hierarchy
- parent-child relationships
- stable board and connection identity
- connection event naming
- database attachment metadata

This folder does not own:

- server lifecycle
- serial transport
- firmware execution
- event listener threads
- MCP transport wiring

## Domain Graph

```mermaid
classDiagram
    class HardwareSystem {
      id
      description
      microcontrollers
      database
    }

    class Microcontroller {
      id
      hardware_system_id
      port
      baud_rate
      fqbn
      connections
      database
    }

    class Connection {
      id
      name
      component_type
      microcontroller_id
      hardware_system_id
      pins
      database
      event_name
    }

    class Database {
      id
      hardware_system_id
      host
      port
      user
      databaseName
    }

    HardwareSystem "1" --> "*" Microcontroller
    HardwareSystem "0..1" --> "0..1" Database
    Microcontroller "1" --> "*" Connection
    Microcontroller "0..1" --> "0..1" Database
    Connection "0..1" --> "0..1" Database
```

## Identity Reactions

`HardwareSystem.id`

- identifies the top-level declared system

`Microcontroller.id`

- is resolved from `config.json["devices"]`
- is not intended to be user-defined directly
- is currently derived by matching the declared `port`

`Connection.microcontroller_id`

- must match the owning microcontroller
- is filled during connection registration if omitted

## Connection Event Name

`Connection.event_name` is the internal identifier used for:

- MCP event routing
- STREAM event routing
- stream table naming
- firmware event output naming

Current format:

```text
<component_type>_<short_microcontroller_hash>_<short_pin_hash>
```

How it is built:

- `component_type` is kept readable
- the owning microcontroller `id` is hashed down to a short stable suffix
- `pins` are canonicalized into a stable signature such as `echo=8,trigger=9`
- that pin signature is hashed down to a short suffix

Why pins are included:

- `component_type + microcontroller_id` is not enough when the same board has two devices of the same type
- adding the pin signature distinguishes physical attachments without relying on mutable fields like `name`

This is intentionally short to avoid PostgreSQL identifier length issues. It is internal identity, not a user-facing label.

Use `name` and `description` for readability.

## Streaming Reactions

Streaming support is device-specific.

- Not every connection should stream data.
- Connections express intent with `stream=True`.
- Harness provisions stream tables from compiled stream contracts.
- `Database` only writes stream data to already-provisioned tables.

This area is still in flux and should be simplified later.
