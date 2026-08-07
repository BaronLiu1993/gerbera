# Review

Analyze persisted experimental data after collection is complete.

Return the review decision inside the required top-level `response` object.

- Run only the SQL or analysis tool calls declared by the current review action.
- Query all variables listed in `data_variables`; do not selectively omit
  contradictory or unexpected records.
- Do not call hardware tools, collect new measurements, or modify stored data.
- Compare the analysis with the review action's `expected` criterion and the
  hypothesis.
- Identify uncertainty, missing data, failed operations, outliers, and
  confounding factors. Never invent values to fill gaps.
- Treat valid contradictory evidence as a falsified hypothesis.
- Treat broken, corrupted, insufficient, or inconclusive data as an
  experimental failure, not as evidence that falsifies the hypothesis.
- Use `accepted` with `next_state: null` when the evidence supports the final
  conclusion and the workflow is complete.
- Use `rejected` with `next_state: null` when the workflow has failed and must
  terminate.
- Use `replan` with `next_state: initialisation` only when another plan is
  required.
- Clearly report whether the evidence supports, falsifies, or cannot resolve
  the hypothesis.
