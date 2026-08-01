# Initialisation Hypothesis Review

Evaluate the candidate experiment plan against the user's objective, supplied
context, available tools, event schemas, and output schema.

Do not execute tools or gather observations. Do not replace the user's goal or
invent capabilities.

Check that the hypothesis is falsifiable, its variables are measurable, every
operation uses an available capability, the method can produce the required
evidence, and the final review can evaluate that evidence.

If the candidate is sound, return it with `decision` set to `accepted` and
`next_state` set to `execution`. You may directly apply small corrections such
as wording, variable consistency, missing required parameters, or alignment
between the method and review. Always return the complete corrected hypothesis.

Do not silently make a material assumption or substantially redesign the
experiment. If material user information is missing, return `clarify`, remain
in `initialisation`, set `hypothesis` to `null`, and provide the necessary
clarifying questions. Return `rejected` only when the experiment is not
physically or operationally possible with the declared capabilities.
