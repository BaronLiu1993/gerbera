from dataclasses import dataclass

from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.driver.subloop.states.session import Session
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.sub_loop.act_runtime import ActRuntime
from gerbera_harness.agent_runtime.sub_loop.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.agent_runtime.sub_loop.planning_runtime import (
    PlanningRuntime,
)
from gerbera_harness.memory.memory import Memory


@dataclass
class SubAgentRuntime:
    session: Session
    model: Model
    memory: Memory
    messages: list[dict[str, object]]
    mcp_url: str
    timeout_seconds: float
    context_window_size: int = 20

    @property
    def observation_runtime(self) -> ObservationRuntime:
        return ObservationRuntime(
            model=self.model,
            messages=self.messages,
            mcp_url=self.mcp_url,
        )

    @property
    def planning_runtime(self) -> PlanningRuntime:
        return PlanningRuntime(
            model=self.model,
            messages=self.messages,
        )

    @property
    def act_runtime(self) -> ActRuntime:
        return ActRuntime(
            messages=self.messages,
            mcp_url=self.mcp_url,
            timeout_seconds=self.timeout_seconds,
        )

    async def run_agent(self):
        while True:
            current_state = self.session.state
            if current_state.state is ExecuteLoopStateEnum.OBSERVE:
                self.observation_runtime.run_observation()
            elif current_state.state is ExecuteLoopStateEnum.PLAN:
                pass
            elif current_state.state is ExecuteLoopStateEnum.ACT:
                pass
            else:
                raise ValueError("Unsupported State")
