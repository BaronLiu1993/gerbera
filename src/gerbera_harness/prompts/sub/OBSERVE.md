# Observation

Use the available observation tools to determine the current physical state.
You may start or stop sensor streams and inference models when needed to
observe the environment. Do not change physical actuator state.
Treat the message history as the source of truth and do not assume that an
action produced its intended physical effect without observing it.

When observation is sufficient, return `finish` with a concise reason, a
concise `summary`, and a flat scalar `result` list describing the observed or
analyzed outcome.

Always include every response field. For a `tool_call`, set `reason` and
`summary` to `null` and `result` to `[]`. For `finish`, set `tool_name` to
`null` and `arguments` to `[]`.

`arguments` and `result` are lists of `{ "key": string, "value": scalar }`
entries.
