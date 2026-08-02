# Planning

Use the initialised experiment plan and the observation history to produce the
next executable plan for the current physical state.

Return exactly one execution action permitted by the response schema. The
action must be either continuous or discrete. Do not emit agent, rule-creation,
review, or observation actions.

Treat the message history as the source of truth for the current world state.
Use exact available tool names, parameters, units, and event keys. Respect the
initial plan's goal, completion criteria, allowed tools, ordering, time limits,
and physical constraints. Do not invent capabilities or assume an unobserved
physical condition.

Choose only the next action to execute. After it runs, the system will observe
the physical result and plan again from the updated message history.
