import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final

from gerbera_harness.memory import EventTypeEnum, Memory


@dataclass(frozen=True)
class ContextBuilder(ABC):
    memory: Memory

    def build_current_task_anchor(self) -> dict[str, object]:
        task = self.memory.get_current_task_state()
        task_payload = task.model_dump(mode="json")
        task_events = [
            event
            for event in self.memory.get_events_state()
            if event.task_id == task.task_id
        ]
        tool_events = [
            event
            for event in task_events
            if event.event_type is EventTypeEnum.TOOL_CALL
        ]

        return {
            "task_id": task_payload["task_id"],
            "task_goal": task_payload["task_goal"],
            "success_criteria": task_payload["success_criteria"],
            "status": task_payload["status"],
            "attempts": task_payload["attempts"],
            "started_at": task_payload["started_at"],
            "finished_at": task_payload["finished_at"],
            "tool_calls": task_payload["tool_calls"],
            "events": [
                event.model_dump(mode="json")
                for event in task_events
            ],
            "tool_results": [
                event.payload
                for event in tool_events
            ],
        }

    @abstractmethod
    def build_runtime_context(self) -> dict[str, object]:
        pass
