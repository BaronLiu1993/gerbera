# railctl

Minimal scaffold for a serial device CLI and SDK.

## Run

```bash
python -m railctl.cli --help
```

## Structure

```text
src/railctl/
  core/          # device and registry primitives
  commands/      # Typer command groups
  cli.py         # root Typer app
tests/           # test suite
```
