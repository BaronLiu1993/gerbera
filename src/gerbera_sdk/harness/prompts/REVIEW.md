# Review

Analyze persisted experimental data after collection is complete.

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
- Transition to `execution` only when another predefined collection step is
  required.
- Transition to `complete` when the evidence supports or falsifies the
  hypothesis and a final conclusion can be recorded.
- Transition to `failed` when the workflow cannot safely or meaningfully
  continue.
