# Source Packages

The `src` folder contains the installable Python packages for Gerbera.

## Packages

```text
gerbera_cli/    Local CLI helpers for board setup and tunnels.
gerbera_sdk/    SDK domain model, firmware generation, runtime server, events.
```

## Flow

```mermaid
flowchart TD
    A[gerbera_cli] --> B[devices.json]
    B --> C[User hardware declaration]
    C --> D[gerbera_sdk]
    D --> E[Firmware and runtime server]
```

## Rule

Keep CLI concerns in `gerbera_cli` and runtime/domain concerns in `gerbera_sdk`.
