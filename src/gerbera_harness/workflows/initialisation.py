import json
from dataclasses import dataclass, field

from gerbera_harness.domain.session import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.workflows.initialisation_process import (
    InitialisationProcess,
)
from gerbera_harness.domain.experiment import (
    HypothesisSchema,
)
from gerbera_harness.domain.responses import (
    InitialisationResponseSchema,
)
from gerbera_harness.infrastructure.llm import Model
from gerbera_harness.workflows.context import (
    InitialisationContextBuilder,
)
from gerbera_harness.domain.responses import (
    Answer,
    Question,
)
from gerbera_harness.memory import Memory
from gerbera_harness.prompts import PromptTypeEnum, load_prompt


INITIALISATION_PROMPT = load_prompt(
    PromptTypeEnum.MAIN,
    "INITIALISATION.md",
)
INITIALISATION_REVIEW_PROMPT = load_prompt(
    PromptTypeEnum.MAIN,
    "INITIALISATION_REVIEW.md",
)


@dataclass(frozen=True)
class InitialisationResult:
    decision: InitialisationDecisionEnum
    requested_next_state: LoopStateEnum
    hypothesis: HypothesisSchema | None
    clarifying_questions: list[Question] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class InitialisationRuntime:
    model: Model
    memory: Memory
    context_builder: InitialisationContextBuilder
    process: InitialisationProcess
    max_attempts: int = 3
    clarifying_questions: list[Question] = field(default_factory=list)

    async def run_initial(
        self,
        user_prompt: str,
        feedback: list[str],
    ) -> InitialisationResult | None:
        client = self.model.get_agent_client()

        if feedback:
            self.memory.append_message(
                "user",
                json.dumps({"review_feedback": feedback}),
            )

        for _ in range(self.max_attempts):
            res = await self.process.run(user_prompt=user_prompt)
            self.memory.append_message("user", res)
            raw_hypothesis = await client.send(
                self.context_builder.build(),
                INITIALISATION_PROMPT,
                HypothesisSchema.model_json_schema(),
            )

            print(raw_hypothesis)

            self.memory.append_message("assistant", raw_hypothesis)
            candidate_hypothesis = self.candidate_hypothesis(raw_hypothesis)

            raw_evaluation = await client.send(
                self.context_builder.build_review_context(
                    candidate_hypothesis
                ),
                INITIALISATION_REVIEW_PROMPT,
                InitialisationResponseSchema.model_json_schema(),
            )

            response = InitialisationResponseSchema.model_validate_json(
                raw_evaluation
            ).response

            self.memory.append_message(
                "assistant",
                response.model_dump_json(),
            )

            decision = response.decision
            requested_next_state = response.next_state

            if decision is InitialisationDecisionEnum.ACCEPTED:
                return InitialisationResult(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    hypothesis=response.hypothesis,
                )
            # Not Physically Possible
            if decision is InitialisationDecisionEnum.REJECTED:
                return InitialisationResult(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    hypothesis=None,
                    rejection_reasons=response.rejection_reasons,
                )

            if decision is InitialisationDecisionEnum.CLARIFY:
                questions = [
                    Question(
                        question=question.question,
                        options=list(question.options),
                    )
                    for question in response.clarifying_questions
                ]
                self.clarifying_questions = questions
                return InitialisationResult(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    hypothesis=None,
                    clarifying_questions=list(self.clarifying_questions),
                )

    def get_questions(self) -> list[Question]:
        return list(self.clarifying_questions)

    def candidate_hypothesis(self, raw_hypothesis: str) -> HypothesisSchema:
        try:
            return HypothesisSchema.model_validate_json(raw_hypothesis)
        except ValueError as exc:
            preview = raw_hypothesis[:500]
            raise RuntimeError(
                "Initialisation did not produce a valid hypothesis: "
                f"{preview}"
            ) from exc

    async def submit_answers(self, answers: list[Answer]):
        answer_ids = [answer.question_id for answer in answers]
        question_ids = [
            question.question_id for question in self.clarifying_questions
        ]
        if (
            len(answers) != len(self.clarifying_questions)
            or sorted(answer_ids) != sorted(question_ids)
        ):
            raise ValueError(
                "Answers must match all clarifying question IDs"
            )

        responses = []

        for answer in answers:
            question = next(
                question
                for question in self.clarifying_questions
                if question.question_id == answer.question_id
            )
            responses.append(
                {
                    "question_id": answer.question_id,
                    "question": question.question,
                    "answer": answer.answer,
                }
            )

        self.memory.append_message(
            "assistant",
            json.dumps({"clarification_answers": responses}),
        )
