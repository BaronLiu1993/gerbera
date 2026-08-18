# AGENTS.md

## Primary Instruction

Follow the user's explicit instructions only.

Do not self-direct extra cleanup, fixes, refactors, validation, or architecture changes unless the user asks for them.

If a requested change reveals adjacent broken code, stale imports, failing tests, or confusing structure, stop after the requested change and report the issue instead of fixing it automatically.

Before making code edits, restate the exact requested scope in one short sentence. Keep edits inside that scope.

## Repo Preferences

- Do not create new `domain/` modules.
- Runtime orchestration belongs under `src/gerbera_harness/runtime/`.
- Memory should stay thin and should not call MCP, construct rich events, or decide workflow lifecycle transitions.
- Do not update tests unless the user explicitly asks.
