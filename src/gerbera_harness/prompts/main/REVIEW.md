# Review

Decide whether the current task succeeded after execution.

Use the provided review context, previous state context, current world state,
hardware state, events, and tool results. Do not invent missing evidence.

Return exactly one decision:

- `success`: the current task is complete.
- `replan_actions`: the current task is still valid, but the last action plan
  failed or the observed environment changed enough that actions should be
  regenerated for the same task.
- `redecompose_tasks`: the current task list is invalid; rebuild high-level
  tasks from the original objective plus this review context.
- `fail`: execution should stop because the task or objective cannot continue
  safely or meaningfully.

Use this decision process:

1. Did the task complete?
2. If not, is the current task still valid?
3. If the current task is valid, choose `replan_actions`.
4. If the current task is invalid, choose `redecompose_tasks`.
5. If continuing would be unsafe or impossible, choose `fail`.

The `context` field should be concise handoff context explaining what happened
and what the next stage needs to know.
