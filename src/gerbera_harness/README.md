# Gerbera harness

The harness executes configurable agent workflows against remote tools. It never
imports `gerbera_sdk`. The SDK and harness communicate through MCP and the small
`gerbera_protocol` wire contract. The CLI configures and starts the services; the
harness process constructs its own models, connectors, extensions, and workflows.

## Workflows

Every graph has engine-owned `__entry__` and `__exit__` nodes. Entry validates
workflow input and initializes isolated run state. Ordinary nodes return an
outcome and JSON output. The graph selects the next node. Exit validates the
public output and produces a terminal result. Exceptions, cancellation, timeouts,
and step limits also terminate through exit.

Two presets ship with the package:

- `simple`: model → tools → model, until the model produces an answer.
- `structured`: decompose → observe → review observation → plan → review plan →
  execute → review execution → evaluate, with explicit retry/replan transitions.

The default is `simple`. The structured preset uses fresh read-only SDK snapshots
for observation and execution review. Its node configuration and prompts live
under [`runtime/workflows/`](runtime/workflows/). The earlier phase runtimes remain
available to existing Python integrations; the REST service uses the graph engine.

## Python API

```python
from gerbera_harness.models.adapters.ollama import OllamaAdapter
from gerbera_harness.models.client import StructuredModelClient
from gerbera_harness.models.settings import ModelConnectionSettings
from gerbera_harness.runtime.contracts import HarnessServices
from gerbera_harness.runtime.harness import Harness, HarnessBuilder
from gerbera_harness.runtime.state_machine.schemas import RunRequest
from gerbera_harness.tools.sources import LocalToolSource

services = HarnessServices(
    model=StructuredModelClient(OllamaAdapter(ModelConnectionSettings(
        model="your-installed-model", endpoint="http://localhost:11434",
    ))),
    tools=LocalToolSource(),
)
harness = Harness.simple(services)
result = await harness.run(
    RunRequest(workflow="simple", input={"prompt": "Hello"})
)
```

`Harness.structured(services)` selects the structured preset. Individual stages
can be swapped without rewriting its graph:

```python
from gerbera_harness.runtime.workflows.presets import StructuredWorkflowBuilder

workflow = (
    StructuredWorkflowBuilder()
    .with_stage("plan", MyPlanningNode())
    .with_stage("evaluate", MyEvaluationNode())
    .build()
)
harness = HarnessBuilder(services).with_workflow(workflow).build()
```

Custom strategies implement `WorkflowNode.execute(state, context)` and return
`NodeResult(outcome=..., output=...)`. Keep per-run data in state and node outputs;
node instances can be shared across concurrent runs. Dependencies are supplied
through `NodeContext`, separate from serializable state.

For reusable graph types, extend `StateMachine` and implement `define_workflow()`
to return a `WorkflowBuilder`. A custom harness can extend `BaseHarness` and supply
`create_execution()`. Both paths use the same engine and entry/exit contracts.

## JSON configuration

The service reads `.gerbera/harness/harness.json`, or the path in
`GERBERA_HARNESS_CONFIG`:

```json
{
  "schema_version": "1",
  "model": {
    "type": "local",
    "provider": "ollama",
    "name": "your-installed-model",
    "endpoint": "http://localhost:11434"
  },
  "connector": {
    "mcp_url": "https://robot.example.com/mcp",
    "physical_state": true
  },
  "default_workflow": "custom",
  "workflows": {"custom": "workflows/custom/workflow.json"},
  "extensions": ["event_recording"]
}
```

For hosted providers, use `type: "api"` and a model name supporting structured
outputs. Registered providers are `openai`, `anthropic`, `google`, `groq`,
`mistral`, `openrouter`, and `xai`. Use `openai_compatible` with an explicit
`endpoint` for another compatible hosted service. The API key comes from the
environment variable named by `model.api_key_env` (default `API_KEY`); it is sent
as a bearer token for OpenAI-compatible services. Secrets are never embedded in
workflow JSON.

For example, the `model` section for Groq is:

```json
{
  "type": "api",
  "provider": "groq",
  "name": "openai/gpt-oss-20b",
  "api_key_env": "GROQ_API_KEY",
  "maximum_tokens": 8192,
  "timeout_seconds": 120
}
```

Local providers remain `ollama` and `openai_compatible`; compatible endpoints
are API base URLs such as `http://localhost:8080/v1`, not full chat-completion
URLs. Local compatible servers can optionally authenticate through `api_key_env`.
Compatible clients send `maximum_tokens` as `max_tokens`, except Groq, which
uses `max_completion_tokens`. Custom services can override this with
`token_limit_parameter`.

Structured-output support depends on the selected model and endpoint; see the
[Groq](https://console.groq.com/docs/structured-outputs),
[Mistral](https://docs.mistral.ai/studio/conversations/structured-output/custom),
[OpenRouter](https://openrouter.ai/docs/guides/features/structured-outputs), and
[xAI](https://docs.x.ai/developers/model-capabilities/text/structured-outputs)
documentation. OpenRouter requests require supporting endpoints. Responses are
validated against the workflow schema; unsupported formats, refusals, and
truncated responses are not silently converted or retried as unstructured text.

Every provider uses `StructuredModelClient`: adapters handle authentication,
protocol-specific requests, and response-text extraction; the shared client
alone parses JSON and validates the workflow output schema. Adapter implementations
live in `models/adapters/`, connection settings in `models/settings.py`, and
provider registration in `models/registry.py`. Register another adapter factory
through `ModelClientRegistry` without changing workflow code. The former
`infrastructure.model_adapters` module re-exports the existing hosted adapters for
Python integrations using that import path.

Custom workflows are optional. Omit `workflows` and set `default_workflow` to
`simple` or `structured` to use a packaged preset. When workflows are supplied,
their names must match their configuration keys, and the default must be present.

### A complete custom workflow

`workflows/custom/workflow.json`:

```json
{
  "schema_version": "1",
  "name": "custom",
  "interface": {
    "input_schema": {
      "type": "object",
      "properties": {"prompt": {"type": "string", "minLength": 1}},
      "required": ["prompt"],
      "additionalProperties": false
    },
    "output_schema": {
      "type": "object",
      "properties": {"message": {"type": "string"}},
      "required": ["message"],
      "additionalProperties": false
    }
  },
  "nodes": {"answer": "nodes/answer.json"},
  "transitions": [
    {"from": "__entry__", "outcome": "start", "to": "answer"},
    {
      "from": "answer", "outcome": "complete", "to": "__exit__",
      "terminal": {
        "status": "succeeded",
        "output": {"message": "/nodes/answer/output/message"}
      }
    }
  ],
  "limits": {"maximum_steps": 20, "maximum_duration_seconds": 300}
}
```

`workflows/custom/nodes/answer.json`:

```json
{
  "schema_version": "1",
  "type": "prompt",
  "config": {
    "prompt": "Answer the supplied prompt. Return JSON matching the schema.",
    "response_schema": {
      "type": "object",
      "properties": {"message": {"type": "string"}},
      "required": ["message"],
      "additionalProperties": false
    }
  },
  "inputs": {"prompt": "/input/prompt"},
  "outcomes": ["complete"],
  "execution": {"timeout_seconds": 60, "maximum_attempts": 1}
}
```

`prompt_file` can replace `prompt` for prompt nodes; paths resolve relative to
the node JSON. Prompt files are loaded when the workflow is compiled. Referenced
files and symlinks must remain inside the harness configuration directory.

Inputs use JSON Pointer into `/input`, `/values`, or `/nodes`. Output bindings map
pointers within a node's output to object paths below `/values/`. For example:

```json
{"outputs": {"/message": "/values/latest_message"}}
```

An empty source pointer (`""`) selects the whole node output. Operational metadata
is stored separately and is never bound to a prompt automatically. Exit mappings
select the public result; the API does not expose the entire working state.

Every declared node outcome must have exactly one transition. Successful exit
transitions require output matching the workflow interface. Failed, cancelled,
and timed-out exits require an error object with `code` and `message`. Cyclic
graphs are allowed and bounded by the run's step and duration limits.

### Node types and extensions

Built-in node types are `prompt`, `agent`, `tool_execution`, `condition`,
`transform`, `observation`, and `subworkflow`. A subworkflow references another
workflow JSON through `config.workflow`; its terminal status becomes the parent
node's outcome. Recursive references are rejected.

Register custom behavior in trusted Python code:

```python
from gerbera_harness.runtime.nodes import NodeFactory

class InspectionExtension:
    def register(self, registry):
        registry.register_node_factory(
            NodeFactory("inspection", InspectionConfig, InspectionNode)
        )

harness = (
    HarnessBuilder(services)
    .with_extension(InspectionExtension())
    .with_workflow_file(workflow_path, configuration_root)
    .build()
)
```

`InspectionConfig` is a Pydantic model validated before `InspectionNode` is
constructed. JSON selects registered names; it cannot import Python modules.
Programmatic graphs and JSON graphs compile to the same representation.

First-party extensions are:

- `HardwareContextExtension`: remote tool capabilities in model context.
- `PhysicalStateProjection`: fresh remote hardware snapshots in model context.
- `DatabaseToolsExtension`: read-only database tools.
- `SandboxExtension`: sandbox tools.
- `EventRecordingExtension`: records internal lifecycle events through `EventStore`.

The physical projection currently uses snapshots at node boundaries. Hardware
event streaming and SSE are deferred. Event handlers are observers; failures are
counted by the event publisher and do not change workflow decisions.

## REST service

Create an application with an injected harness:

```python
from gerbera_harness.api.app import create_app

app = create_app(harness)
```

For configured deployment, use the bootstrap factory:

```bash
uvicorn gerbera_harness.bootstrap:create_server_app --factory --host 0.0.0.0 --port 8000
```

The bootstrap validates the remote manifest and discovers tools during startup.
`gerbera init --with-harness` creates a harness configuration and the CLI mounts
it read-only when starting the harness container. Workflow files are interpreted
by the harness process.

The configured server exposes `/ready` separately from `/health`. Readiness
requires successful startup/tool discovery and, when an SDK connector is
configured, a ready `gerbera://readiness` report from that SDK. Dependency checks
are bounded; an unavailable SDK makes the harness unready rather than healthy
merely because HTTP is listening. `MCP_URL` is the deployment override for the
connector endpoint. The CLI launches and polls this server; it does not construct
models, validate workflows, or execute agent runs.

Start a run:

```http
POST /runs
Content-Type: application/json

{"workflow":"custom","input":{"prompt":"Inspect the object"}}
```

The response is `202 Accepted` with a run ID. Poll using `GET /runs/{run_id}`.
Cancel using `POST /runs/{run_id}/cancel`. Retrieve bounded event history using
`GET /runs/{run_id}/events?after=0&limit=100`. Events have monotonic per-run IDs;
`truncated` indicates that older events have been evicted. `GET /health` reports
process liveness. `/inference` accepts the same request and waits for completion.

Runs continue independently of individual HTTP requests. Application shutdown
cancels active runs and waits for cleanup. Run state and event retention are
bounded and in memory; they do not survive a process restart. Use one server
worker with this run manager. Persistent or multi-worker execution requires a
different store/manager implementation. No streaming HTTP transport is included.

## Package boundaries

```text
bootstrap → adapters + extensions + runtime → contracts
api → run manager → workflow engine → node strategies
connector → MCP + gerbera_protocol
SDK server → gerbera_protocol
```

`runtime/state_machine/` owns graph validation, loading, entry, exit, and execution.
`runtime/nodes/` owns reusable node strategies and their configuration schemas.
`memory/` is retained for earlier structured runtime integrations; the new engine
uses thin per-run JSON state and keeps projections in extensions.

Legacy agent orchestration also lives under `runtime/`, with its API import
retained as a compatibility facade. Temporal reconstruction is a runtime
projection, not a responsibility of memory. Deployment orchestration belongs to
the CLI and is not exported by `gerbera_harness.runtime`.
