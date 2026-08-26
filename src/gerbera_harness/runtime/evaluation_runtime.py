import json
from dataclasses import dataclass

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.runtime.context import EvaluateContextBuilder
from gerbera_harness.runtime.schemas import EvaluationResultSchema


EVALUATION_PROMPT = load_prompt(PromptTypeEnum.MAIN, "EVALUATION.md")


@dataclass
class EvaluationRuntime:
    model: Model
    memory: Memory
    context_builder: EvaluateContextBuilder

    async def run_evaluation(self) -> EvaluationResultSchema:
        client = self.model.get_agent_client()
        context = {
            "evaluation_context": self.context_builder.build_runtime_context(),
        }

        raw_response = await client.send(
            [
                {
                    "role": "user",
                    "content": json.dumps(context, indent=2),
                }
            ],
            EVALUATION_PROMPT,
            EvaluationResultSchema.model_json_schema(),
        )

        return EvaluationResultSchema.model_validate_json(raw_response)
