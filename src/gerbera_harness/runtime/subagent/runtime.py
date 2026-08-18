import asyncio
from dataclasses import dataclass, field

from gerbera_harness.runtime.session import (
    ExecuteDecisionEnum,
)
from gerbera_harness.runtime.schemas.execution import (
    ExecuteErrorSchema,
)
from gerbera_harness.runtime.schemas.execute import (
    ExecutionTypeEnum,
)

from gerbera_harness.runtime.subagent.schemas import (
    ExecuteLoopStateEnum,
    ObservationStatusEnum,
    PlanningExecuteActionSchema,
    PlanningStatusEnum,
    Session,
    SubAgentResult,
    ToolCallStatusEnum,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.runtime.subagent.context import (
    ObservationPromptContextBuilder,
    PlanningPromptContextBuilder,
    SubAgentContext,
)
from gerbera_harness.runtime.subagent.act_runtime import ActRuntime
from gerbera_harness.runtime.subagent.observe_runtime import (
    ObservationRuntime,
)
from gerbera_harness.runtime.subagent.planning_runtime import (
    PlanningRuntime,
)
from gerbera_harness.memory.schemas.world import WorldStateSchema
from gerbera_harness.tools.registry import LocalToolRegistry


@dataclass
class SubAgentRuntime:
    session: Session
    model: Model
    context: SubAgentContext
    mcp_url: str
    timeout_seconds: float
    local_tool_registry: LocalToolRegistry
    context_window_size: int = 20
    max_turns: int = 20
    turns_completed: int = 0
    action_plan: PlanningExecuteActionSchema | None = None
    errors: list[ExecuteErrorSchema] = field(default_factory=list)
    previous_act_error: ExecuteErrorSchema | None = None
    messages: list[dict[str, object]] = field(default_factory=list)
    observations: list[WorldStateSchema] = field(default_factory=list)
    tool_events: list[dict[str, object]] = field(default_factory=list)

    @property
    def observation_runtime(self) -> ObservationRuntime:
        return ObservationRuntime(
            model=self.model,
            mcp_url=self.mcp_url,
            context_builder=ObservationPromptContextBuilder(
                context=self.context,
                messages=self.messages,
                observations=self.observations,
                tool_events=self.tool_events,
                context_window_size=self.context_window_size,
                available_tools=tuple(self.local_tool_registry.list_tools()),
            ),
            messages=self.messages,
            observations=self.observations,
            tool_events=self.tool_events,
            local_tool_registry=self.local_tool_registry,
        )

    @property
    def planning_runtime(self) -> PlanningRuntime:
        return PlanningRuntime(
            model=self.model,
            context_builder=PlanningPromptContextBuilder(
                context=self.context,
                messages=self.messages,
                observations=self.observations,
                tool_events=self.tool_events,
                context_window_size=self.context_window_size,
                previous_act_error=self.previous_act_error,
                available_tools=tuple(self.local_tool_registry.list_tools()),
            ),
            messages=self.messages,
            on_action_planned=lambda action_plan: setattr(
                self, "action_plan", action_plan
            ),
        )

    @property
    def act_runtime(self) -> ActRuntime:
        return ActRuntime(
            mcp_url=self.mcp_url,
            timeout_seconds=self.timeout_seconds,
            messages=self.messages,
            tool_events=self.tool_events,
            local_tool_registry=self.local_tool_registry,
        )

    async def run_agent(self) -> SubAgentResult:
        try:
            return await asyncio.wait_for(
                self._run_agent_loop(),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            error = TimeoutError(
                "Subagent task timed out after "
                f"{self.timeout_seconds} seconds"
            )
            self._append_error(str(error))
            return self._result(ExecuteDecisionEnum.REJECTED)
        except Exception as exc:
            self._append_error(str(exc))
            return self._result(ExecuteDecisionEnum.REJECTED)

    async def _run_agent_loop(self) -> SubAgentResult:
        while self.turns_completed < self.max_turns:
            current_state = self.session.state
            if current_state.state is ExecuteLoopStateEnum.OBSERVE:
                decision = await self.observation_runtime.run_observation()
                self.turns_completed += 1

                if decision is ObservationStatusEnum.READY:
                    self.session.perform_transition(ExecuteLoopStateEnum.PLAN)
                elif decision is ObservationStatusEnum.COMPLETE:
                    return self._result(ExecuteDecisionEnum.ACCEPTED)
                elif decision is ObservationStatusEnum.BLOCKED:
                    self._append_error("Observation blocked")
                    return self._result(ExecuteDecisionEnum.REJECTED)
            elif current_state.state is ExecuteLoopStateEnum.PLAN:
                decision = await self.planning_runtime.run_planning()
                self.turns_completed += 1

                if decision is PlanningStatusEnum.READY:
                    self.session.perform_transition(ExecuteLoopStateEnum.ACT)
                elif decision is PlanningStatusEnum.BLOCKED:
                    self._append_error("Planning blocked")
                    return self._result(ExecuteDecisionEnum.REJECTED)
                elif decision is PlanningStatusEnum.COMPLETE:
                    return self._result(ExecuteDecisionEnum.ACCEPTED)
            elif current_state.state is ExecuteLoopStateEnum.ACT:
                if self.action_plan is None:
                    raise RuntimeError("An action plan is required to act")

                act_runtime = self.act_runtime
                status = await act_runtime.run_action(self.action_plan)
                self.turns_completed += 1

                if status is ToolCallStatusEnum.SUCCESS:
                    self.previous_act_error = None
                elif status in {
                    ToolCallStatusEnum.FAILED,
                    ToolCallStatusEnum.TIMED_OUT,
                }:
                    self.previous_act_error = self._append_error(
                        act_runtime.last_event.error_message,
                        event_name=act_runtime.last_event.tool_name,
                    )

                if status in {
                    ToolCallStatusEnum.SUCCESS,
                    ToolCallStatusEnum.FAILED,
                    ToolCallStatusEnum.TIMED_OUT,
                }:
                    self.session.perform_transition(ExecuteLoopStateEnum.OBSERVE)
            else:
                raise ValueError("Unsupported State")

        reason = f"Subagent exceeded its maximum of {self.max_turns} turns"
        self._append_error(reason)
        return self._result(ExecuteDecisionEnum.REJECTED)

    def _result(self, decision: ExecuteDecisionEnum) -> SubAgentResult:
        return SubAgentResult(
            decision=decision,
            errors=(
                list(self.errors)
                if decision is ExecuteDecisionEnum.REJECTED
                else []
            ),
            turns_completed=self.turns_completed,
            observations=list(self.observations),
            tool_events=[dict(event) for event in self.tool_events],
        )

    def _append_error(
        self,
        error: str,
        *,
        event_name: str | None = None,
    ) -> ExecuteErrorSchema:
        execute_error = ExecuteErrorSchema(
            event_name=(event_name or self.session.state.state.value),
            event_type=ExecutionTypeEnum.AGENT,
            position=self.turns_completed,
            error=error,
        )
        self.errors.append(execute_error)
        return execute_error
