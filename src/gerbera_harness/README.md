# Harness

The harness owns agent reasoning and orchestration around Gerbera hardware.

## Package Layout

```text
api/             HTTP application and session orchestration
domain/          Schemas, experiment models, events, and state machines
infrastructure/  LLM, MCP, database, and sandbox adapters
memory/          Robot memory state and memory schemas
prompts/         Main-loop and adaptive-loop system prompts
tools/           Agent-facing local tools and their registry
workflows/       Planning, execution, review, and adaptive runtimes
```

## Dependency Direction

```text
api -> workflows -> domain
                -> memory
                -> tools -> infrastructure
workflows       -> infrastructure
```

Domain modules must not depend on workflow, API, or infrastructure modules.
Memory owns robot state; workflows decide how events and state drive execution.

## Runtime Flow

```text
API request
  -> workflow coordinator
  -> initialisation and planning
  -> deterministic execution or adaptive observe-plan-act execution
  -> review
```

The old `agent/driver` package-level exports remain temporarily available as
compatibility surfaces, but their definitions now live in `domain/`.
