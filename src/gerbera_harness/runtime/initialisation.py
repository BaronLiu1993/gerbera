import json
from dataclasses import dataclass, field

import httpx

from gerbera_harness.runtime.session import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)
from gerbera_harness.runtime.schemas.experiment import (
    HypothesisSchema,
)
from gerbera_harness.runtime.schemas.initialisation import (
    InitialisationResponseSchema,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.runtime.schemas.initialisation import (
    Answer,
    Question,
)
from gerbera_harness.memory import Memory
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.tools.client import ToolClient


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
    tool_client: ToolClient
    max_attempts: int = 3
    urls: list[str] = field(default_factory=list)
    clarifying_questions: list[Question] = field(default_factory=list)

    async def run_initial(
        self,
        # feedback: list[str],
    ) -> InitialisationResult | None:
        client = self.model.get_agent_client()

        for _ in range(self.max_attempts):
            res = await self.build_agent_context()
            self.memory.append_message("user", res)
            raw_hypothesis = await client.send(
                self.build_context(),
                INITIALISATION_PROMPT,
                HypothesisSchema.model_json_schema(),
            )

            print(raw_hypothesis)

            self.memory.append_message("assistant", raw_hypothesis)
            candidate_hypothesis = self.candidate_hypothesis(raw_hypothesis)

            raw_evaluation = await client.send(
                self.build_review_context(candidate_hypothesis),
                INITIALISATION_REVIEW_PROMPT,
                InitialisationResponseSchema.model_json_schema(),
            )

            response = InitialisationResponseSchema.model_validate_json(
                raw_evaluation
            ).response

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

    async def submit_answers(self, answers: list[Answer]):
        pass
        # answer_ids = [answer.question_id for answer in answers]
        # question_ids = [
        #     question.question_id for question in self.clarifying_questions
        # ]
        # if (
        #     len(answers) != len(self.clarifying_questions)
        #     or sorted(answer_ids) != sorted(question_ids)
        # ):
        #     raise ValueError(
        #         "Answers must match all clarifying question IDs"
        #     )

        # responses = []

        # for answer in answers:
        #     question = next(
        #         question
        #         for question in self.clarifying_questions
        #         if question.question_id == answer.question_id
        #     )
            

    async def build_agent_context(self) -> str:
        tools = await self.tool_client.list_tools()
        sources: dict[str, str] = {}
        for url in self.urls:
            sources[url] = await self.fetch_url(url)

        return self.generate_agent_context(
            objective=self.memory_objective(),
            tools=tools,
            sources=sources,
        )

    def generate_agent_context(
        self,
        objective: str,
        tools: list,
        sources: dict[str, str],
    ) -> str:
        sections = [
            "# Experiment Context",
            "## Objective",
            objective.strip(),
        ]

        sections.append("## Available Tools")
        for tool in tools:
            sections.append(f"### {tool.name}")
            sections.append(tool.description)
            sections.append("```json")
            sections.append(json.dumps(tool.input_schema, indent=2))
            sections.append("```")

        sections.append("## Research Sources")
        if not sources:
            sections.append("No research sources were provided.")

        for url, content in sources.items():
            sections.append(f"### {url}")
            sections.append(content.strip())

        return "\n\n".join(sections)

    async def fetch_url(self, fetch_url: str) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(fetch_url)
        response.raise_for_status()
        return response.text
