import json
from dataclasses import dataclass

from gerbera_harness.domain.experiment import (
    HypothesisSchema,
)
from gerbera_harness.workflows.context.base import ContextBuilder


@dataclass(frozen=True)
class InitialisationContextBuilder(ContextBuilder):
    def build_runtime_context(self) -> dict[str, object]:
        return {
            "phase": "initialisation",
            "goal": self.memory.goal,
        }

    def build_review_context(
        self,
        candidate_hypothesis: HypothesisSchema,
    ) -> list[dict[str, object]]:
        latest_world_state = self.memory.latest_world_state()
        context_message = {
            "role": "user",
            "content": json.dumps(
                {
                    "runtime_context": {
                        "phase": "initialisation_review",
                        "goal": self.memory.goal,
                        "candidate_hypothesis": (
                            candidate_hypothesis.model_dump(mode="json")
                        ),
                        "latest_world_state": (
                            latest_world_state.model_dump(mode="json")
                            if latest_world_state
                            else None
                        ),
                    }
                }
            ),
        }

        if self.context_window_size == 0:
            return [context_message]

        return [
            context_message,
            *(dict(message) for message in self.memory.messages[
                -self.context_window_size :
            ]),
        ]
