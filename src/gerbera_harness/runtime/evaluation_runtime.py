from dataclasses import dataclass

from gerbera_harness.memory import Memory


@dataclass
class EvaluationRuntime:
    memory: Memory

    async def run_evaluation(self) -> None:
        pass
