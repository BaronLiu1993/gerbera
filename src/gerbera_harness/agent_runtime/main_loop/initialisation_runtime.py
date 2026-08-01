import json
from dataclasses import dataclass, field

from gerbera_harness.agent.driver.main_loop import (
    InitialistationDecisionEnum as InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.agent.driver.main_loop.processes.initialisation_process import (
    InitialisationProcess,
)
from gerbera_harness.agent.driver.main_loop.schema.hypothesis.hypothesis_schema import (
    HypothesisSchema,
)
from gerbera_harness.agent.driver.main_loop.schema.initialisation.initialisation_response_schema import (
    InitialisationResponseSchema,
)
from gerbera_harness.agent.model.model import Model
from gerbera_harness.agent_runtime.main_loop.utils import append_message
from gerbera_harness.agent.driver.main_loop.schema.initialisation.clarification_schema import (
    Answer,
    Question,
)


@dataclass(frozen=True)
class InitialisationResult:
    decision: InitialisationDecisionEnum
    requested_next_state: LoopStateEnum
    hypothesis: HypothesisSchema | None
    clarifying_questions: list[Question] = field(default_factory=list)


@dataclass
class InitialisationRuntime:
    model: Model
    messages: list[dict[str, object]]
    max_attempts: int = 3
    clarifying_questions: dict[str, Question] = field(default_factory=list)

    async def run_initial(
        self,
        user_prompt: str,
        system_prompt: str,
    ) -> InitialisationResult | None:
        client = self.model.get_agent_client()

        for _ in range(self.max_attempts):
            res = InitialisationProcess.run(user_prompt=user_prompt)
            append_message(
                self.messages,
                role="user",
                content=res,
            )
            raw_hypothesis = client.send(
                self.messages,
                system_prompt,
                HypothesisSchema.model_json_schema(),
            )
            message = json.loads(raw_hypothesis)

            append_message(
                self.messages,
                role="assistant",
                content=message,
            )

            hypothesis = HypothesisSchema.model_validate(raw_hypothesis.hypothesis)

            raw_evaluation = client.send(
                self.messages,
                system_prompt,
                InitialisationResponseSchema.model_json_schema(),
            )

            response = InitialisationResponseSchema.model_validate(raw_evaluation)

            append_message(
                self.messages,
                role="assistant",
                content=json.dumps(response),
            )

            decision = response.decision
            requested_next_state = response.next_state

            if decision is InitialisationDecisionEnum.ACCEPTED:
                return InitialisationResult(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    hypothesis=hypothesis,
                )
            # Not Physically Possible
            if decision is InitialisationDecisionEnum.REJECTED:
                return InitialisationResult(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    hypothesis=None,
                )

            if decision is InitialisationDecisionEnum.CLARIFY:
                self.clarifying_questions = [
                    Question(
                        question=question.question,
                        options=list(question.options),
                    )
                    for question in response.clarifying_questions
                ]
                return InitialisationResult(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    hypothesis=None,
                    clarifying_questions=list(self.clarifying_questions),
                )

    def get_questions(self) -> list[Question]:
        return list(self.clarifying_questions)

    async def submit_answers(self, answers: list[Answer]):
        if len(answers) != len(self.clarifying_questions):
            raise ValueError("Incorrect Amount of Clarifying Questions")

        responses = []

        for answer in answers:
            responses.append(
                {
                    "question_id": answer.question_id,
                    "question": answer.question,
                    "answer": answer.answer,
                }
            )

        append_message(
            self.messages,
            role="assistant",
            content=json.dumps({"clarification_answers": responses}),
        )
