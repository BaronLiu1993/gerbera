# Setup

This folder owns local runtime bring-up after hardware has been declared.

The setup flow loads the configured hardware object, provisions the board, starts the local HTTP runtime, starts ngrok, and writes local/public endpoints back into `config.json`.

## Ownership

This folder may own:

- loading the hardware object from `config.json`
- installing firmware dependencies
- flashing firmware
- starting the local HTTP runtime
- starting and stopping ngrok
- writing server endpoint metadata into `config.json`

This folder should not own:

- device discovery and registration
- hardware model definitions
- external agent deployment logic
- cloud orchestration beyond local runtime exposure

## Flow

```mermaid
flowchart TD
    A[config.json] --> B[Load hardware object]
    B --> C[Flash firmware]
    C --> D[Start local HTTP runtime]
    D --> E[Start ngrok]
    E --> F[Write local/public endpoints to config.json]
```
