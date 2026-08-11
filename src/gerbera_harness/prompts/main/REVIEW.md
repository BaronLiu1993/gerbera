# Review

Evaluate experimental evidence after execution is complete.

Return the review decision inside the required top-level `response` object.

- Do not execute tools, run SQL, query the database, call hardware tools,
  collect new measurements, or modify stored data.
- Use only evidence already present in the provided context, including
  execution observations and recorded tool results.
- Compare the analysis with the review action's `expected` criterion and the
  hypothesis.
- Identify uncertainty, missing data, failed operations, outliers, and
  confounding factors. Never invent values to fill gaps.
- If required database query results or analysis summaries are missing from
  the execution evidence, reject as an experimental failure due to missing
  evidence. Do not claim you attempted or could execute the query in review.
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
