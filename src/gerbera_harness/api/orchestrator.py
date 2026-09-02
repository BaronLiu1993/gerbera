from dataclasses import dataclass, field

from gerbera_harness.runtime.agent_runtime import AgentRuntime
from gerbera_harness.runtime.session import Session
from gerbera_harness.infrastructure.model import Model, ModelProviderEnum
from gerbera_harness.memory import (
    EventStateSchema,
    Memory,
    PhysicalConfigurationStateSchema,
    TemporalStateSchema,
    WorldStateSchema,
)
from gerbera_harness.runtime.execute_consumer_runtime import ExecuteConsumerRuntime
from gerbera_harness.tools.client import ToolClient
from gerbera_harness.tools.registry import LocalToolRegistry


@dataclass
class Orchestrator:
    local_tool_registry: LocalToolRegistry
    sessions: dict[str, AgentRuntime] = field(default_factory=dict)

    def initialise_agent_runtimes(
        self,
        user_prompt: str,
        mcp_url: str,
        provider: str,
        api_key: str,
        model: str,
    ) -> AgentRuntime:
        runtime = self.build_agent_runtime(
            user_prompt=user_prompt,
            mcp_url=mcp_url,
            provider=provider,
            api_key=api_key,
            model=model,
        )
        self.sessions[runtime.session.session_id] = runtime
        return runtime

    def build_agent_runtime(
        self,
        user_prompt: str,
        mcp_url: str,
        provider: str,
        api_key: str,
        model: str,
    ) -> AgentRuntime:
        session = Session()
        memory = Memory(
            session_id=session.session_id,
            world_state=WorldStateSchema(session_id=session.session_id),
            temporal_state=TemporalStateSchema(session_id=session.session_id),
            task_state=None,
            events_state=EventStateSchema(session_id=session.session_id),
            physical_configuration=PhysicalConfigurationStateSchema(
                session_id=session.session_id,
            ),
        )
        runtime_model = Model(
            model_provider=ModelProviderEnum(provider),
            model=model,
            api_key=api_key,
        )
        tool_client = ToolClient(
            mcp_url=mcp_url,
            local_tool_registry=self.local_tool_registry,
        )
        execute_consumer = ExecuteConsumerRuntime(
            tool_client=tool_client,
            memory=memory,
        )
        runtime = AgentRuntime(
            session=session,
            model=runtime_model,
            memory=memory,
            tool_client=tool_client,
            user_prompt=user_prompt,
            execute_consumer=execute_consumer,
        )
        return runtime
