# Reactions

Reactions let any MCP client configure hardware-event automation through the
standalone Gerbera MCP server. They do not depend on `gerbera_harness` and do
not make an HTTP request back to the server.

The server exposes three reaction management tools:

- `create_reaction`
- `list_reactions`
- `delete_reaction`

Use `list_reaction_events` to discover valid event routes before creating a
reaction. A reaction selects one field from an event payload, compares that
field with a typed expected value, and invokes an existing state-changing tool
registered by the same server.

## Create schema

```json
{
  "reaction": {
    "event": {
      "event_type": "STREAM",
      "microcontroller_id": "board-1",
      "event_name": "temperature_sensor",
      "payload_field": "temperature"
    },
    "condition": {
      "operator": "greater_than",
      "expected_value": 30
    },
    "action": {
      "tool_name": "turn_off_heater",
      "arguments": {}
    },
    "trigger_mode": "continuous",
    "cooldown_seconds": 10
  }
}
```

Supported operators are `equal`, `not_equal`, `less_than`,
`less_than_equal`, `greater_than`, and `greater_than_equal`. Ordered
comparisons require a numeric expected value. Equality comparisons also
support booleans and strings.

`trigger_mode` controls the lifecycle:

- `once` removes the reaction before invoking its action, so it executes at
  most once even if the action fails.
- `continuous` keeps the reaction active until `delete_reaction` is called.
  `cooldown_seconds` limits how often it can run, and one reaction never
  overlaps itself.

Read-only tools and the reaction management tools cannot be used as actions.
Action names and arguments are validated when the reaction is created.

## Persistence

Each definition is stored as `.gerbera/reactions/<reaction_id>.json` and is
restored when the Gerbera MCP server starts. Runtime observations such as the
latest value, trigger count, result, and error are returned by
`list_reactions`; they are not persisted across restarts.

Deleting a reaction removes it from memory and deletes its definition file.
