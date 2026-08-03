import asyncio
from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop.schema.execute.execution_event_schema import (
    ExecuteErrorSchema,
    ExecutionTypeEnum,
)

from gerbera_harness.agent.driver.subloop.schema.act import (
    ToolCallStatusEnum,
)
from gerbera_harness.agent.driver.subloop.schema.observe import (
    ObservationStatusEnum,
)
from gerbera_harness.agent.driver.subloop.schema.plan import (
    PlanningExecuteActionSchema,
    PlanningStatusEnum,
)
from gerbera_harness.agent.driver.subloop.states.base import (
    ExecuteLoopStateEnum,
)
from gerbera_harness.agent.driver.subloop.states.session import Session
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.context_builder import (
    ObservationContextBuilder,
    PlanningContextBuilder,
)
from gerbera_harness.agent_runtime.sub_loop.act_runtime import ActRuntime
from gerbera_harness.agent_runtime.sub_loop.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.agent_runtime.sub_loop.planning_runtime import (
    PlanningRuntime,
)
from gerbera_harness.memory import Memory


@dataclass
class SubAgentRuntime:
    session: Session
    model: Model
    memory: Memory
    mcp_url: str
    timeout_seconds: float
    context_window_size: int = 20
    max_turns: int = 20
    turns_completed: int = 0
    action_plan: PlanningExecuteActionSchema | None = None
    errors: list[ExecuteErrorSchema] = field(default_factory=list)

    @property
    def observation_runtime(self) -> ObservationRuntime:
        return ObservationRuntime(
            model=self.model,
            memory=self.memory,
            mcp_url=self.mcp_url,
            context_builder=ObservationContextBuilder(
                memory=self.memory,
                context_window_size=self.context_window_size,
            ),
        )

    @property
    def planning_runtime(self) -> PlanningRuntime:
        return PlanningRuntime(
            model=self.model,
            memory=self.memory,
            context_builder=PlanningContextBuilder(
                memory=self.memory,
                context_window_size=self.context_window_size,
            ),
            on_action_planned=lambda action_plan: setattr(
                self, "action_plan", action_plan
            ),
        )

    @property
    def act_runtime(self) -> ActRuntime:
        return ActRuntime(
            memory=self.memory,
            mcp_url=self.mcp_url,
            timeout_seconds=self.timeout_seconds,
        )

    async def run_agent(self) -> None:
        try:
            await asyncio.wait_for(
                self._run_agent_loop(),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            error = TimeoutError(
                "Subagent task timed out after "
                f"{self.timeout_seconds} seconds"
            )
            self._append_error(str(error))
            raise error from exc
        except Exception as exc:
            self._append_error(str(exc))
            raise

    async def _run_agent_loop(self) -> None:
        while self.turns_completed < self.max_turns:
            current_state = self.session.state
            if current_state.state is ExecuteLoopStateEnum.OBSERVE:
                decision = await self.observation_runtime.run_observation()
                self.turns_completed += 1

                if decision is ObservationStatusEnum.READY:
                    self.session.perform_transition(ExecuteLoopStateEnum.PLAN)
                elif decision is ObservationStatusEnum.COMPLETE:
                    self.memory.complete_task()
                    return
                elif decision is ObservationStatusEnum.BLOCKED:
                    self._append_error("Observation blocked")
                    return
            elif current_state.state is ExecuteLoopStateEnum.PLAN:
                decision = await self.planning_runtime.run_planning()
                self.turns_completed += 1

                if decision is PlanningStatusEnum.READY:
                    self.session.perform_transition(ExecuteLoopStateEnum.ACT)
                elif decision is PlanningStatusEnum.BLOCKED:
                    self._append_error("Planning blocked")
                    return
                elif decision is PlanningStatusEnum.COMPLETE:
                    return
            elif current_state.state is ExecuteLoopStateEnum.ACT:
                if self.action_plan is None:
                    raise RuntimeError("An action plan is required to act")

                act_runtime = self.act_runtime
                status = await act_runtime.run_action(self.action_plan)
                self.turns_completed += 1

                if status in {
                    ToolCallStatusEnum.FAILED,
                    ToolCallStatusEnum.TIMED_OUT,
                }:
                    self._append_error(
                        act_runtime.last_event.error_message,
                        event_name=act_runtime.last_event.tool_name,
                    )

                if status in {
                    ToolCallStatusEnum.SUCCESS,
                    ToolCallStatusEnum.FAILED,
                    ToolCallStatusEnum.TIMED_OUT,
                }:
                    self.session.perform_transition(
                        ExecuteLoopStateEnum.OBSERVE
                    )
            else:
                raise ValueError("Unsupported State")

        raise RuntimeError(
            f"Subagent exceeded its maximum of {self.max_turns} turns"
        )

    def _append_error(
        self,
        error: str,
        *,
        event_name: str | None = None,
    ) -> None:
        self.errors.append(
            ExecuteErrorSchema(
                event_name=(
                    event_name or self.session.state.state.value
                ),
                event_type=ExecutionTypeEnum.AGENT,
                position=self.turns_completed,
                error=error,
            )
        )
