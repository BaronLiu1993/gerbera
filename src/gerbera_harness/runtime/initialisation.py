import json
from dataclasses import dataclass, field

import httpx

from gerbera_harness.runtime.session import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)

from gerbera_harness.runtime.schemas.initialisation import (
    InitialisationResponseSchema,
    InitialisationResultSchema,
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
    "INITIALISATION_REVIEW.md",
)

@dataclass
class InitialisationRuntime:
    model: Model
    memory: Memory
    tool_client: ToolClient
    max_attempts: int = 3
    urls: list[str] = field(default_factory=list)
    clarifying_questions: dict[str, tuple[Question, Answer] | None]= field(default_factory=dict)

    async def run_initial(
        self,
        feedback: str,  # initial user prompt can be that too
    ) -> InitialisationResultSchema:
        client = self.model.get_agent_client()

        for _ in range(self.max_attempts):
            initial_context = await self.build_agent_context(feedback)

            raw_evaluation = await client.send(
                initial_context,
                INITIALISATION_PROMPT,
                InitialisationResponseSchema.model_json_schema(),
            )

            response = InitialisationResponseSchema.model_validate_json(
                raw_evaluation
            ).response

            decision = response.decision
            requested_next_state = response.next_state
            questions = response.clarifying_questions

            if decision is InitialisationDecisionEnum.ACCEPTED:
                return InitialisationResultSchema(
                    decision=decision,
                    requested_next_state=requested_next_state,
                )
            # Not Physically Possible
            if decision is InitialisationDecisionEnum.REJECTED:
                return InitialisationResultSchema(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    rejection_reasons=response.rejection_reasons,
                )

            if decision is InitialisationDecisionEnum.CLARIFY:
                for question in questions:
                    self.clarifying_questions[question.question_id] = None
                return InitialisationResultSchema(
                    decision=decision,
                    requested_next_state=requested_next_state,
                    clarifying_questions=list(self.clarifying_questions),
                )

    async def submit_answers(self, question_answer_pair: list[tuple[Question, Answer]]) -> None:
        for pair in question_answer_pair:
            question_id = pair[0].question_id
            if question_id in self.clarifying_questions:
                self.clarifying_questions[question_id] = question_answer_pair

    async def fetch_url(self, fetch_url: str) -> str:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(fetch_url)
            response.raise_for_status()
            return response.text

    async def build_agent_context(self, feedback) -> str:
        tools = await self.tool_client.list_tools()
        sources: dict[str, str] = {}
        for url in self.urls:
            sources[url] = await self.fetch_url(url)

        return self.generate_agent_context(
            clarifying_questions=self.clarifying_questions,
            feedback=feedback,
            tools=tools,
            sources=sources,
        )

    def generate_agent_context(
        self,
        clarifying_questions: dict[str, tuple[Question, Answer] | None],
        feedback: str,
        tools: list,
        sources: dict[str, str],
    ) -> str:
        sections = [
            "# Experiment Context",
            "## Objective",
            feedback.strip(),
        ]

        sections.append("## Clarifying Questions")
        if not clarifying_questions:
            sections.append("No clarifying questions have been asked.")

        for question_id, question_answer in clarifying_questions.items():
            if question_answer is None:
                sections.append(f"### {question_id}")
                sections.append("No answer has been provided.")
                continue

            question, answer = question_answer
            sections.append(f"### {question_id}")
            sections.append(f"Question: {question.question}")
            sections.append(f"Answer: {answer.answer}")

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

    
