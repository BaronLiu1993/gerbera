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
  - `execute`: perform a bounded, repeatable experimental protocol. It may set
    up hardware, run one or more trial tool calls, capture outputs, return the
    hardware to its baseline state, and repeat. It does not interpret results.
  - `observe`: monitor an experiment that remains active over minutes or hours
    and record how its outputs change over time. It does not manipulate the
    independent variable or judge the hypothesis.
  - `review`: compare the analysis with the hypothesis and its expected result,
    then determine whether the evidence supports, falsifies, or cannot yet resolve
    the hypothesis.
- Write every variable name in lowercase `snake_case`, with underscores between
  words.
- For `review`, set `expected` to the expected result or acceptance criterion.
- For `execute` and `observe`, set `expected` to `null`.
- Make the first checklist action an `execute` action.
- Define the evidence required for completion or failure.
- Do not execute any step or claim any observation.

## Execute Contract

Each `execute` action defines one repeatable trial condition:

- `independent_variables` lists the variables deliberately manipulated by the
  trial. Every entry includes its exact value and unit.
- `dependent_variables` lists the variables measured by tool responses. Set
  `value` to `null` during initialisation because no measurement exists yet.
  Always specify the measurement unit, or `null` when dimensionless.
- `setup_calls` contains tool calls performed once before the first repetition.
  Use an empty list when no setup is required.
- `trial_calls` contains the ordered tool calls performed during every
  repetition. It must contain at least one call.
- `reset_calls` contains the ordered tool calls that restore the original
  baseline after every repetition, including the final repetition. Use an empty
  list only when the trial cannot alter persistent hardware state.
- `repetitions` is the number of times to perform the complete trial-and-reset
  cycle and must be at least one.

Every tool call must:

- Set `tool` to an exact available hardware tool name.
- Represent each tool input as an `arguments` entry containing the MCP parameter
  name, its concrete value, and the independent or controlled variable it
  represents. Set `variable` to `null` only for operational parameters.
- Map each relevant MCP response field to a dependent variable through
  `captures`. Use an empty list when the call produces no experimental
  measurement.
- Use only parameters and response fields declared by the tool schemas. Never
  invent tools, parameters, or output fields.

Create separate execute steps when testing different independent-variable
values. For example, servo angles `0`, `90`, and `180` are three trial
conditions, each with its own execute action and reset protocol.

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
