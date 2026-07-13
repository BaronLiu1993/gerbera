# Legacy Firmware Function Folder

This folder is retained for compatibility while active firmware generation lives in `src/gerbera_sdk/firmware`.

The active firmware modules are:

```text
firmware/generator.py
firmware/parser.py
firmware/routing.py
firmware/flash.py
firmware/devices/
```

## Ownership

This folder should not receive new device builder work.

New firmware behavior should go into:

- `src/gerbera_sdk/firmware/devices/` for component-specific builders
- `src/gerbera_sdk/firmware/routing.py` for setup/loop routing
- `src/gerbera_sdk/firmware/parser.py` for command parsing
- `src/gerbera_sdk/firmware/generator.py` for sketch assembly

## Migration Rule

If code here is still used, move it up into `src/gerbera_sdk/firmware/` before extending it.
