# Test structure

- `unit/` tests branching and validation within one class or function.
- `integration/` tests collaboration across runtime, event, database, firmware, or CLI boundaries.

Run the suites independently with:

```bash
pytest tests/unit
pytest tests/integration
```

Tests use fakes at physical boundaries. They do not require a serial device,
PostgreSQL server, Arduino CLI installation, or running MCP server.
