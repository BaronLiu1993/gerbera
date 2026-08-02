Review the observation agent's request to finish.
Return `complete` only when the gathered observations show that the objective
has been achieved. Return `ready` when the gathered information is sufficient
to plan another action and the objective has not yet been achieved. Return
`blocked` when a physical limitation prevents further progress. Return
`continue` when more observation is needed, with concise feedback explaining
what information is still missing.
