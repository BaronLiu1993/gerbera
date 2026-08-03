# Observation

Use the available read-only tools to determine the current physical state.
Treat the message history as the source of truth and do not assume that an
action produced its intended physical effect without observing it.

When observation is sufficient, return `finish` with a concise reason and a
complete `world_state` snapshot describing the currently observed environment.
