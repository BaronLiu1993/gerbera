import json
from dataclasses import dataclass, field

from gerbera_harness.infrastructure.model import Model
from gerbera_harness.tools.client import ToolClient
from gerbera_harness.prompts import PromptTypeEnum, load_prompt

EXECUTION_PROMPT = load_prompt(
    PromptTypeEnum.MAIN,
    "EXECUTION.md",
)

@dataclass
class ExecuteProducer:
    model: Model
    tool_client: ToolClient
    messages: list[dict[str, object]] = field(default_factory=list)

    @cached_property
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
    
        @cached_property
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

    async def produce_action_groups(
        self,
        intent_context: str,
    ) -> list[ExecuteActionGroupSchema]:
        client = self.model.get_agent_client()

        while True:
            
            # context = await self.build_context(intent_context)
            raw_response = await client.send(
                context,
                EXECUTION_PROMPT,
                ExecuteProducerResponseSchema.model_json_schema(),
            )
            response = ExecuteProducerResponseSchema.model_validate_json(
                raw_response
            )

            return response.action_groups
