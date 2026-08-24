# Harness

The harness owns agent reasoning and orchestration around Gerbera hardware.

## Package Layout

```text
api/             HTTP application and session orchestration
infrastructure/  LLM, MCP, database, and sandbox adapters
memory/          Thin memory API and memory-owned schemas
runtime/         Agent runtime, session state, task_decomposition, execution, review, context builders, schemas, and subagents
runtime/context/ Prompt context builders
runtime/schemas/ Runtime-owned action, experiment, response, and execution schemas
runtime/subagent/ Bounded observe-plan-act subagent runtime
runtime/subagent/context/ Subagent context model and state-specific prompt context builders
runtime/subagent/schemas/ Subagent states, tool-call, observation, and planning schemas
runtime/utils.py Shared runtime schema helpers
prompts/         Main-loop and subagent system prompts
tools/           Agent-facing local tools and their registry
```

## Dependency Direction

```text
api -> runtime -> memory
                -> tools -> infrastructure
runtime -> infrastructure
```

Memory owns current state and recent history; runtime decides how events and state drive execution.

## Runtime Flow

```text
API request
  -> agent runtime
  -> task_decomposition and planning
  -> deterministic execution or bounded subagent observe-plan-act execution
  -> review
```
