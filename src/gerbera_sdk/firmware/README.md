# Firmware

Firmware operations are explicit and independent:

- `FirmwareGenerator`: renders a microcontroller declaration into a sketch and serial helpers.
- `FirmwareUploader`: installs dependencies, compiles sketches, and uploads builds through Arduino CLI.

Device-specific pin setup, commands, and streaming remain in the device YAML files.
`devices/library.py` owns rendering and device lookup; `boards/definitions.py` owns
board definitions and lookup. There are no separate factory, abstract builder, or
forwarding modules in the firmware pipeline.
The shared sketch template, including serial parsing and response helpers, lives
in `sketch.ino.template`.

Generated firmware initializes devices and inactive outputs, then accepts commands
and emits sensor streams. It has no handshake, contract digest, component checks,
sessions, or heartbeat watchdog. Disconnecting the host does not stop actuators.

```python
from gerbera_sdk.gerbera_runtime import GerberaRuntime

GerberaRuntime.install_dependencies(hardware_system)
sketches = GerberaRuntime.generate_firmware(hardware_system)
builds = GerberaRuntime.compile_firmware(hardware_system, sketches)
GerberaRuntime.upload_firmware(hardware_system, builds)
```

Each board produces one `.gerbera/firmware/<board-id>/<board-id>.ino` file. Compilation writes a `build` directory alongside the sketch.
Generation replaces the obsolete generated runtime/component/command files.

Commands and responses retain command IDs:

```text
WRITE,status_led,state:1,command_id:<id>
MCP,<event_name>,command_id:<id>,led_state:1
STREAM,<event_name>,distance:12.4
```
