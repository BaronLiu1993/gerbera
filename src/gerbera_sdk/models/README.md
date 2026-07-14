# Models

READ: we will need to clean up the code for this modelling. It is messy right now and does not fully reflect the intended user experience yet. THE SOURCE OF TRUTH FOR MICROCONTROLLERS IS THE DEVICE.JSON FILE

The models folder owns the hardware declaration graph and the database model used by the runtime.

Models should stay focused on:

- relationships
- identity
- validation
- database metadata

## Files

```text
hardware_system.py      Top-level hardware declaration.
microcontroller.py      Board identity resolved from devices.json via port.
connection.py           One declared device connection on a board.
database.py             PostgreSQL connection details and table helpers.
table.py                In-memory table metadata.
pin.py                  Pin model support.
```

## Ownership

This folder owns:

- hardware hierarchy
- parent-child relationships
- stable board and connection identity
- connection event naming
- database attachment metadata
- database table creation helpers

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

## Identity Rules

`HardwareSystem.id`

- identifies the top-level declared system

`Microcontroller.id`

- is resolved from `devices.json`
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
<component_type>_<short_microcontroller_hash>
```

This is intentionally short to avoid PostgreSQL identifier length issues. It is internal identity, not a user-facing label.

Use `name` and `description` for readability.

## Database Rules

Database support is device-specific.

- Not every connection should receive a database.
- Only builders marked as database-compatible should create stream tables.
- A hardware system can define one database at the top level.
- That database may be propagated downward only when the device builder supports database streaming.

This area is still in flux and should be simplified later.
