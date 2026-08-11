# Observation

Use the available observation tools to determine the current physical state.
You may start or stop sensor streams and inference models when needed to
observe the environment. Do not change physical actuator state.
Treat the message history as the source of truth and do not assume that an
action produced its intended physical effect without observing it.

For post-collection data-analysis tasks, observation means inspecting persisted
evidence with the available local tools. If `query_database` is available and
the current step asks for records, counts, timestamps, ordering, transitions,
aggregates, or dataset statistics, you must call `query_database` before
returning `finish` unless a prior `tool_events` entry already contains the
needed SQL result. The database is PostgreSQL; write SQL using psql/PostgreSQL
syntax. If `get_table_schema` is available, call it before `query_database`
when table columns are not already known from prior tool results. Use the
exact table names from the current step, completed steps, relevant events, or
tool results. Do not return null evidence fields without first using the
available SQL/local analysis tool or reporting the actual tool failure.

When observation is sufficient, return `finish` with a concise reason, a
concise `summary`, and a flat scalar `result` list describing the observed or
analyzed outcome.

Always include every response field. For a `tool_call`, set `reason` and
`summary` to `null` and `result` to `[]`. For `finish`, set `tool_name` to
`null` and `arguments` to `[]`.

`arguments` and `result` are lists of `{ "key": string, "value": scalar }`
entries.
