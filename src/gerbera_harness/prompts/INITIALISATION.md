# Initialisation

Create the immutable research foundation and an ordered experimental workflow.

- Define the objective and a falsifiable hypothesis.
- Identify independent and dependent variables, assumptions, and constraints.
- Inspect the available tools and establish that the experiment is feasible
  before producing the workflow.
- Treat an available tool's input schema as authoritative evidence of what the
  system can execute. Initialisation plans tool calls but does not execute them.
- Research sources are optional. Their absence is not a reason to reject an
  experiment when the objective and available tool schemas provide enough
  information.
- Produce an ordered checklist and classify every action by its single role:
  - `execute`: manipulate variables and collect data with hardware tools. It
    does not interpret results.
  - `review`: after data collection is complete, query the persisted results
    with SQL or analysis tools and compare them with the expected result. It
    must not collect new hardware data.
- Write every variable name in lowercase `snake_case`, with underscores between
  words.
- Put `expected` inside each `review` action. Ordinary execute actions do not
  have an `expected` field; `RuleCreationSchema.expected` is the rule's
  comparison value and is the only exception.
- Make the first checklist action an `execute` action.
- Make the final checklist action a `review` action.
- If the workflow uses a rule, register it before any action that can emit the
  watched event or depends on the rule's callback.
- Define the evidence required for completion or failure.
- Do not execute any step or claim any observation.

## Rule Planning

A rule is a deterministic runtime check with the form:

`when actual_event_value <operator> expected_value, run callback`

The condition compares one incoming hardware event value with one concrete,
finite numeric `expected` value. The runtime converts the watched sensor value
to `float` before evaluating the condition and passes that float to the
callback. A rule must not perform interpretation, probabilistic reasoning, or
post-experiment analysis.

When the method requires this conditional behaviour:

- Use `RuleCreationSchema`, with `action_type` set to `execute` and
  `execution_type` set to `rule`. A rule stays active across later execute
  groups and does not have a `duration_seconds`.
- Set `create_tool_call` to the exact available rule-creation tool and
  `delete_tool_call` to the exact available rule-deletion tool. The executor
  creates the rule when it reaches this action and deletes it after all execute
  groups finish, including when a later group fails.
- Put rule registration in the first execute group. It may share that group
  with ordinary execute actions because the executor always creates every rule
  in the group before starting any of its other actions.
- Register every required rule before starting a stream, monitoring an event,
  applying a stimulus, or performing any other action that could emit its
  watched event.
- Set `event_key.event_type`, `event_key.microcontroller_id`, and
  `event_key.event_name` from the available event and tool context. Do not
  invent an event key. For every rule, `event_key.event_type` must be
  `STREAM`. Never use an `MCP` event for a rule because MCP events are tool
  command responses, not the continuous sensor readings watched by rules.
- Set a concrete numeric `expected` and use only an operator accepted by the
  tool schema, such as `equal`, `not_equal`, `less_than`, `greater_than`,
  `less_than_equal`, or `greater_than_equal`.
- Set `trigger_mode` to `once` when the side effect should happen only for the
  first matching event after registration. Use `repeat` only when the callback
  must run for every matching event while the rule remains registered. Prefer
  `once` for one-time actuator commands such as moving a servo to a target
  angle.
- Put only the Python function body in `callable`. Do not include `async def`,
  the callback name, parameters, imports, or outer indentation. The runtime
  always imports `httpx` and `Client` from `fastmcp`. It also injects `mcp_url`
  from the configured runtime endpoint and passes the watched sensor reading
  as a finite float in `value`. Do not hardcode or reassign either parameter.
  For a no-op callback, use:

  `return None`

  For an MCP call, use `async with Client(mcp_url) as client`, await
  `client.call_tool` with the exact available tool name and argument shape,
  check `result.is_error`, and return `result.data`. For HTTP calls, use
  `httpx.AsyncClient`, await all I/O, set an explicit timeout, and check the
  response status.

  The body is transported as an escaped JSON string in the plan and sent as
  the MCP `callback_body` argument. The runtime validates it, places it inside
  the fixed `async def callback(mcp_url, value):` template, and writes the
  resulting script to a local `.py` file. Do not put a local path in the plan
  and do not claim the file already exists.
- Account for the current rule model: one condition per rule and one rule per
  event key. Do not plan multiple rules for the same event key.
- Do not use a rule as a substitute for the final `review` action. A rule
  reacts during execution; review analyzes persisted evidence after collection.

If no deterministic condition-triggered response is needed, do not create a
rule.

## Execute Contract

Each `execute` action must set `action_type` to `execute`. Deterministic execute
actions classify `execution_type` as `continuous` or `discrete` and list the
dependent and independent variable names involved. Rule creation actions use
`execution_type: rule` and the fields defined in the Rule Planning section.

Choose the execution type from the experiment's data-collection semantics:

- You MUST use `continuous` when the objective involves a duration, change over
  time, repeated timestamped readings, streaming, monitoring, trends,
  stability, or variation during an interval.
- An ordinary `continuous` action runs for a positive `duration_seconds`. Its
  `forward_tool_call` starts collection or streaming and its
  `reverse_tool_call` stops it safely. Use the corresponding start/stop stream
  tools when they are available. Declare every observation channel produced
  while it runs in `emitted_event_keys`; use an empty list if it emits none.
  Streamed observations arrive through those event channels rather than as one
  final tool result. `RuleCreationSchema` is the exception because its lifetime
  spans the remaining execute groups.
- You MUST use `discrete` only for a single bounded command or one-shot reading
  that does not collect a time series. A discrete action defines one
  `forward_tool_call` and its parameter list.
- Do not represent a time-series experiment as one or more discrete readings
  when continuous streaming tools are available.
- If a tool description names a database table for collected stream data, use
  that table in the later review action.

Example: measuring whether an IR sensor output remains stable over 30 seconds
is `continuous`, with the stream-on tool as `forward_tool_call`, the stream-off
tool as `reverse_tool_call`, and `duration_seconds` set to `30`.

Every ordinary execute tool call must:

- Set the tool-call field to an exact available tool name.
- Represent every input as a parameter containing its lowercase snake_case
  `variable`, concrete `value`, `unit` (or `null` when dimensionless), and
  scalar `type`.
- Use only parameters declared by the tool schemas. Never invent tools or
  parameters.

Parameter-list fields are mandatory and must never be omitted:

- Every `discrete` action must include `params`. Add one entry for every input
  required by its `forward_tool_call`. Use `params: []` when that tool accepts
  no inputs.
- Every ordinary `continuous` action must include both `forward_tool_call_params` and
  `reverse_tool_call_params`. Add one entry for every input required by the
  corresponding tool. Use an empty list for either tool when it accepts no
  inputs.
- Never omit a parameter-list field merely because its list is empty.

Use `execution_type: agent` only when the next action cannot be determined
before runtime. Define its `goal`, concrete `completion_criteria`, observed
`input_event_keys`, `allowed_tool_calls`, positive `max_iterations`, and
positive `timeout_seconds`. These bounds contain its observe-decide-act loop.

`RuleCreationSchema` does not use parameter-list fields. The executor maps its
event key, condition, and callable fields to the create and delete tool
arguments.

Create separate execute steps when testing different independent-variable
values.

## Review Contract

A `review` action is a post-collection analysis plan:

- Set `action_type` to `review`.
- Describe the question to answer in `analysis_goal`.
- List the independent and dependent variables in their corresponding fields.
  Every variable entry must include `variable`, `table_name`, `unit`, and
  scalar `type`.
- Copy `table_name` exactly from the database table named in the relevant
  hardware tool description.
- Set `expected` to the hypothesis-derived result or acceptance criterion.
- Query and analyze existing persisted data only. Do not include execution
  fields or hardware collection calls in a review action.

## Readiness Decision

Set `decision` to `accepted`, `next_state` to `execution`, and return the
complete hypothesis when:

- Every required hardware operation maps to an available tool.
- Every planned tool call can be constructed from the tool's input schema.
- The resulting tool responses provide data that can be observed and reviewed
  against the hypothesis.

Set `decision` to `rejected`, `next_state` to `initialisation`, and `response`
to `null` only when:

- A required hardware operation has no available tool.
- A required tool parameter or its valid values cannot be determined.
- The available tool responses cannot produce evidence relevant to the
  hypothesis.

Do not reject merely because the tools have not been executed yet or because no
research sources were provided.
