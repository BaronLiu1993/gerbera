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
- Put `expected` inside each `review` action. Execute actions do not have an
  `expected` field.
- Make the first checklist action an `execute` action.
- Make the final checklist action a `review` action.
- Define the evidence required for completion or failure.
- Do not execute any step or claim any observation.

## Execute Contract

Each `execute` action must set `action_type` to `execute`, classify its
`execution_type` as `continuous` or `discrete`, and list the dependent and
independent variable names involved.

- A `continuous` action runs for a positive `duration_seconds`. It defines a
  `forward_tool_call` that starts the operation and a `reverse_tool_call` that
  safely stops or reverses it, each with its own parameter list.
- A `discrete` action defines one `forward_tool_call` and its parameter list.

Every tool call must:

- Set the tool-call field to an exact available tool name.
- Represent every input as a parameter containing its lowercase snake_case
  `variable`, concrete `value`, `unit` (or `null` when dimensionless), and
  scalar `type`.
- Use only parameters declared by the tool schemas. Never invent tools or
  parameters.

Create separate execute steps when testing different independent-variable
values.

## Review Contract

A `review` action is a post-collection analysis plan:

- Set `action_type` to `review`.
- Describe the question to answer in `analysis_goal`.
- List every collected variable needed for the analysis in `data_variables`.
- Put the ordered SQL or analysis operations in `review_tool_calls`. Each call
  names an exact available analysis tool and supplies its parameters.
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
