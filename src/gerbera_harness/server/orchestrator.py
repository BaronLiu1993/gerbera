from gerbera_harness.agent_runtime.agent_runtime import AgentRuntime
from gerbera_harness.agent.driver.main_loop import Session
from gerbera_harness.agent.model.model import Model, ModelProviderEnum
from gerbera_harness.gateway.database_gateway import DatabaseGateway
from gerbera_harness.gateway.sandbox_gateway import SandboxGateway
from gerbera_harness.memory import Memory
from gerbera_harness.tools.database import QueryDatabaseTool
from gerbera_harness.tools.registry import LocalToolRegistry
from gerbera_harness.tools.sandbox import RunSandboxTool

from dataclasses import field, dataclass


@dataclass
class Orchestrator:
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
        database: DatabaseGateway,
    ):
        session = Session()
        memory = Memory(
            goal=user_prompt,
            session_id=session.session_id,
        )
        model = Model(
            model_provider=ModelProviderEnum(provider),
            model=model,
            api_key=api_key,
        )
        local_tool_registry = LocalToolRegistry()
        local_tool_registry.register(QueryDatabaseTool(database))
        local_tool_registry.register(
            RunSandboxTool(
                session_id=session.session_id,
                sandbox=SandboxGateway(),
            )
        )
        runtime = AgentRuntime(
            session=session,
            model=model,
            memory=memory,
            mcp_url=mcp_url,
            local_tool_registry=local_tool_registry,
        )
        self.sessions[session.session_id] = runtime
        return runtime
