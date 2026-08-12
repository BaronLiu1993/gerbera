# Planning

Use the initialised experiment plan and the observation history to produce the
next executable plan for the current physical state.

Return exactly one execution action permitted by the response schema. The
action must be either continuous or discrete. Do not emit agent, reaction-creation,
review, or observation actions.

Treat the message history as the source of truth for the current world state.
Use exact available tool names, parameters, units, and event keys. Respect the
initial plan's goal, completion criteria, allowed tools, ordering, time limits,
and physical constraints. Do not invent capabilities or assume an unobserved
physical condition.

If this subagent's goal is post-collection data analysis, use available local
analysis tools such as `get_table_schemas` and `query_database` to produce the
evidence requested by the completion criteria. The database is PostgreSQL; use
psql/PostgreSQL SQL syntax. Query only the exact table names and columns
available in context, and plan a schema lookup first when the columns are not
already known. Prefer one read-only SQL query that returns the records, counts,
ordering, transitions, aggregates, or summary needed by the final review. Do
not call hardware tools or collect new measurements for an analysis-only goal.

For every tool argument, set `tool_parameter` to the exact input name from the
selected tool schema. For example, a servo command can use `angle` with a value
of `180`.

Choose only the next action to execute. After it runs, the system will observe
the physical result and plan again from the updated message history.

If `previous_act_error` is present in the runtime context, diagnose it using
the latest observation and adjust the next action. Do not repeat the failed
action unchanged unless the latest observation provides evidence that retrying
it is appropriate. If `previous_act_error` is null, plan normally.
