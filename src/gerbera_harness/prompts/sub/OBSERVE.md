# Observation

Use the available observation tools to determine the current physical state.
You may start or stop sensor streams and inference models when needed to
observe the environment. Do not change physical actuator state.
Treat the message history as the source of truth and do not assume that an
action produced its intended physical effect without observing it.

When observation is sufficient, return `finish` with a concise reason and a
complete `world_state` snapshot describing the currently observed environment.
