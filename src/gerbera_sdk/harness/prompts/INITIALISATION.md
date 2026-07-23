# Initialisation

Create the immutable research foundation and an ordered experimental workflow.

- Define the objective and a falsifiable hypothesis.
- Identify independent and dependent variables, assumptions, and constraints.
- Inspect the available tools and establish that the experiment is feasible
  before producing the workflow.
- Produce an ordered checklist and classify every action by its single role:
  - `execute`: perform an operation that collects experimental data. It does not
    interpret the result or decide whether the hypothesis is supported.
  - `observe`: analyze only the data already collected by execution. It does not
    operate hardware, collect new data, or judge the hypothesis.
  - `review`: compare the analysis with the hypothesis and its expected result,
    then determine whether the evidence supports, falsifies, or cannot yet resolve
    the hypothesis.
- Represent action parameters as a list of variable and typed value pairs.
- Write every variable name in lowercase `snake_case`, with underscores between
  words.
- Set every `execute` target to the exact name of an available hardware tool.
  Never invent tools or represent manual work as an executable action.
- For `review`, set `expected` to the expected result or acceptance criterion.
- For `execute` and `observe`, set `expected` to `null`.
- Make the first checklist action an `execute` action.
- Define the evidence required for completion or failure.
- Do not execute any step or claim any observation.
- Set `decision` to `accepted`, `next_state` to `execution`, and return the
  complete hypothesis when the context is sufficient.
- Set `decision` to `rejected`, `next_state` to `initialisation`, and `response`
  to `null` when the context is insufficient.
