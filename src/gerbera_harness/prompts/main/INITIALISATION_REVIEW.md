# Initialisation Review

Evaluate the generated initialisation intent frame.

Return the decision inside the required top-level `response` object. Do not
produce tasks, action groups, hypotheses, methods, or tool-call plans.

## Accept

Use `accepted` with `next_state: execution` when:

- the user intent is clear enough to begin;
- success criteria are understandable;
- available tools and constraints are represented truthfully; and
- there is no obvious impossibility or safety blocker.

## Clarify

Use `clarify` with `next_state: initialisation` when missing information would
materially change the goal, success criteria, safety constraints, or required
capabilities.

Ask concise questions the user can answer. Do not ask the user to provide an
execution plan.

## Reject

Use `rejected` with `next_state: initialisation` when the requested goal is
clearly impossible, unsupported by available capabilities, or unsafe to begin.

Give concrete rejection reasons grounded in the provided context.
