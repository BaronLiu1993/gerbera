# Initialisation

Generate the current initialisation intent frame for the requested run.

Initialisation is for research, context gathering, and intent framing only. It
does not create tasks, action groups, tool-call plans, hypotheses, methods, or
review programs.

Return only the fields allowed by the response schema.

## Responsibilities

- Identify what the user is trying to achieve.
- Restate the concrete goal execution should later pursue.
- Summarize relevant context from the provided experiment context.
- Capture assumptions that execution and review should know.
- Capture constraints, safety boundaries, and tool/capability limitations.
- Define success criteria for deciding whether the overall goal is achieved.
- Summarize available tools by name and capability.

## Boundaries

- Do not operate hardware.
- Do not call tools.
- Do not claim the world has been observed unless the context says so.
- Do not generate ordered tasks or action sequences.
- Do not output a hypothesis or experimental method.
- Do not invent tool names, parameters, measurements, or physical state.

The output should help execution answer: "Given this intent and the current
world state, what bounded action program should be generated next?"
