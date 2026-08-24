# Review

Decide whether the current task succeeded after execution.

Use the provided review context, previous state context, current world state,
hardware state, events, and tool results. Do not invent missing evidence.

Return exactly one decision:

- `success`: the current task is complete.
- `replan`: the current task did not complete, but the original objective is
  still achievable with a better task decomposition.
- `fail`: execution should stop because the task or objective cannot continue
  safely or meaningfully.

The `context` field should be concise handoff context. If the decision is
`replan`, include what was attempted, what failed, and what task decomposition
should know next.
