from dataclasses import dataclass

from gerbera_harness.memory import Memory
from gerbera_harness.memory.schemas.task import TaskSchema
from gerbera_harness.runtime.subagent.context.models import SubAgentContext


@dataclass(frozen=True)
class SubAgentContextBuilder:
    memory: Memory
    context_window_size: int = 20

    def build(
        self,
        *,
        current_task: TaskSchema,
        workflow_position: int,
    ) -> SubAgentContext:
        hypothesis = self.memory.current_hypothesis
        if hypothesis is None:
            raise RuntimeError("Subagent context requires a hypothesis")

        return SubAgentContext(
            session_id=self.memory.session_id,
            goal=self.memory.goal,
            hypothesis=hypothesis,
            current_task=current_task.task,
            workflow_position=workflow_position,
            completed_tasks=tuple(
                self._recent(self.memory.completed_tasks)
            ),
            world_states=tuple(
                self._recent(self.memory.world_state_ledger)
            ),
            relevant_events=tuple(
                self._recent(self.memory.event_ledger)
            ),
        )

    def _recent(self, values: list) -> list:
        if self.context_window_size == 0:
            return []
        return values[-self.context_window_size :]
