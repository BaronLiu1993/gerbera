from dataclasses import dataclass

from gerbera_harness.runtime.session import (
    InitialisationDecisionEnum,
    LoopStateEnum,
    Session,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.memory import Memory
from gerbera_harness.tools.client import ToolClient
from gerbera_harness.runtime.evaluation_runtime import EvaluationRuntime
from gerbera_harness.runtime.execute_consumer_runtime import ExecuteConsumerRuntime
from gerbera_harness.runtime.execute_producer.session import StateMachine
from gerbera_harness.runtime.execute_producer_runtime import ExecuteProducerRuntime
from gerbera_harness.runtime.initialisation_runtime import (
    InitialisationRuntime,
)


@dataclass
class AgentRuntime:
    session: Session
    model: Model
    memory: Memory
    tool_client: ToolClient
    execute_consumer: ExecuteConsumerRuntime

    async def run_agent(self, initial_user_prompt: str) -> None:
        while True:
            current_state = self.session.state
            if current_state.state is LoopStateEnum.INITIALISATION:
                await self.run_initialisation(initial_user_prompt)
            elif current_state.state is LoopStateEnum.EXECUTION:
                await self.run_execution()
            elif current_state.state is LoopStateEnum.EVALUATION:
                await self.run_evaluation()
                break
            else:
                raise ValueError("Unsupported Main Loop State Enum")

    async def run_initialisation(self, initial_user_prompt: str) -> None:
        result = await InitialisationRuntime(
            model=self.model,
            memory=self.memory,
            tool_client=self.tool_client,
            user_prompt=initial_user_prompt,
        ).run_initial(source_urls=[])

        if result.decision is InitialisationDecisionEnum.ACCEPTED:
            self.session.perform_transition(LoopStateEnum.EXECUTION)
            return

        raise ValueError("Unsupported Initialisation Decision")

    async def run_execution(self) -> None:
        await ExecuteProducerRuntime(
            model=self.model,
            tool_client=self.tool_client,
            memory=self.memory,
            context=self.memory.task_state.goal,
            execute_consumer=self.execute_consumer,
            state_machine=StateMachine(),
        ).produce_action_groups()
        self.session.perform_transition(LoopStateEnum.EVALUATION)

    async def run_evaluation(self) -> None:
        await EvaluationRuntime(memory=self.memory).run_evaluation()
