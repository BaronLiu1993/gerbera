Review the observation agent's request to finish.
Return `ready` when the gathered information is sufficient. Return `blocked`
when a physical limitation makes further observation impossible. Return
`continue` when more observation is needed, with concise feedback explaining
what information is still missing.
