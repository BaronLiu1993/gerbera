from dataclasses import dataclass

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.runtime.context import ObservationContextBuilder
from gerbera_harness.runtime.execute_consumer import ExecuteConsumer
from gerbera_harness.runtime.execute_producer.schemas.observe import (
    ObservationAction,
    ObservationResult,
)
from gerbera_harness.runtime.execute_producer.schemas.states import LoopDecision

OBSERVATION_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "OBSERVE.md",
)


@dataclass
class ObservationRuntime:
    model: Model
    memory: Memory
    tool_client: ToolClient
    execute_consumer: ExecuteConsumer
    context_builder: ObservationContextBuilder
    objective: str # what do we want to gain from observing 
    max_attempts: int = 20

    async def run_observation(self) -> ObservationResult:
        client = self.model.get_agent_client()
        before_context = self.context_builder.build_runtime_context()
        context = {
            "objective": self.objective,
            "context": before_context,
        }

        for _ in range(self.max_attempts):
            raw_response = await client.send(
                context,
                OBSERVATION_PROMPT,
                ObservationAction.model_json_schema(),
            )
            action = ObservationAction.model_validate_json(raw_response)
            await self.execute_consumer.execute_action_groups(
                action.action_groups
            )

            # update the world state
            world_state = await self.memory.define_world_state()
            self.memory.update_world_state(world_state)
            self.memory.rebuild_temporal_state()

            
            # for now lets just say it is always accepted, no error handling for now
            return ObservationResult(
                summary=action.summary,
                result=LoopDecision.SUCCESS,
            )

        # only code happy path for now
        # return ObservationResult(summary="", result=LoopDecision.FAIL)
