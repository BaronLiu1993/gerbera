from dataclasses import dataclass, field

from gerbera_harness.workflows.agent_runtime import AgentRuntime
from gerbera_harness.domain.session import Session
from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.infrastructure.model import Model, ModelProviderEnum
from gerbera_harness.memory import (
    EventStateSchema,
    HardwareConfigurationStateSchema,
    Memory,
    TaskStateSchema,
    TemporalStateSchema,
    WorldStateSchema,
)
from gerbera_harness.tools.registry import LocalToolRegistry


@dataclass
class Orchestrator:
    local_tool_registry: LocalToolRegistry
    sessions: dict[str, AgentRuntime] = field(default_factory=dict)

    # Fix this up later
    # def get_all_agent_runtime(self):
    #     return self.sessions

    def initialise_agent_runtimes(
        self,
        user_prompt: str,
        mcp_url: str,
        provider: str,
        api_key: str,
        model: str,
    ):
        session = Session()
        mcp_client = MCPClient(mcp_url)
        memory = Memory(
            session_id=session.session_id,
            user_goal=user_prompt,
            world_state=WorldStateSchema(session_id=session.session_id),
            temporal_state=TemporalStateSchema(
                session_id=session.session_id,
                current_hardware_configuration={},
            ),
            task_state=TaskStateSchema(),
            events_state=EventStateSchema(session_id=session.session_id),
            hardware_configuration=HardwareConfigurationStateSchema(
                session_id=session.session_id,
                description="",
            ),
            mcp_client=mcp_client,
        )
        model = Model(
            model_provider=ModelProviderEnum(provider),
            model=model,
            api_key=api_key,
        )
        runtime = AgentRuntime(
            session=session,
            model=model,
            memory=memory,
            mcp_url=mcp_url,
            local_tool_registry=self.local_tool_registry,
        )
        self.sessions[session.session_id] = runtime
        return runtime
