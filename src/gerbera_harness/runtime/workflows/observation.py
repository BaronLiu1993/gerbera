from dataclasses import dataclass

from gerbera_harness.runtime.contracts import NodeContext
from gerbera_harness.runtime.nodes.prompt import PromptConfig, PromptNode
from gerbera_harness.runtime.nodes.tools import ToolExecutionConfig, ToolExecutionNode
from gerbera_harness.runtime.state_machine.schemas import NodeResult, WorkflowState


class ObservationConfig(PromptConfig):
    tools: tuple[str, ...] = (
        "get_current_environment_state", "get_current_hardware_state",
    )


@dataclass(frozen=True)
class ObservationNode:
    config: ObservationConfig

    async def execute(
        self, state: WorkflowState, context: NodeContext,
    ) -> NodeResult:
        execution = ToolExecutionNode(ToolExecutionConfig(access="read_only"))
        tool_context = NodeContext(
            context.services, context.emit,
            {"calls": [{"name": name, "arguments": {}} for name in self.config.tools]},
        )
        result = await execution.execute(state, tool_context)
        prompt_context = NodeContext(
            context.services, context.emit,
            {**context.input, "evidence": result.output}, context.extra,
        )
        prompt = PromptConfig.model_validate(
            self.config.model_dump(exclude={"tools"})
        )
        return await PromptNode(prompt).execute(state, prompt_context)
