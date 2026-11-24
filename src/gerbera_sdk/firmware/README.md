# Firmware

Firmware operations are explicit and independent:

- `FirmwareGenerator`: renders a microcontroller declaration into a sketch and serial helpers.
- `FirmwareUploader`: installs dependencies, compiles sketches, and uploads builds through Arduino CLI.

[firmware_config.py](../config/firmware_config.py) maps each component type to its YAML file in [config/firmware](../config/firmware/).
The generator combines that file's behavior with the board and connection settings
and renders `sketch.ino.template`.

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

Host writes target a connection ID. The board acknowledges writes with `MCP`
messages and sends `STREAM` readings while streaming is enabled.

```text
WRITE,status_led,state:1
MCP,status_led,led_state:1
WRITE,front_distance,stream_enabled:1
MCP,front_distance,stream_enabled:1
STREAM,front_distance,distance:12.4
WRITE,front_distance,stream_enabled:0
MCP,front_distance,stream_enabled:0
```
