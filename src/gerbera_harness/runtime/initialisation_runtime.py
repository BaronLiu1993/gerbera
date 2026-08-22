import json
from dataclasses import dataclass, field

import httpx

from gerbera_harness.runtime.session import (
    InitialisationDecisionEnum,
    LoopStateEnum,
)

from gerbera_harness.runtime.schemas.initialisation import (
    InitialisationIntentSchema,
    InitialisationResultSchema,
)
from gerbera_harness.infrastructure.model import Model
from gerbera_harness.runtime.schemas.initialisation import (
    Answer,
    Question,
)
from gerbera_harness.memory import Memory, TaskSchema, TaskStatusEnum
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.tools.client import ToolClient

INITIALISATION_PROMPT = load_prompt(
    PromptTypeEnum.MAIN,
    "INITIALISATION.md",
)


@dataclass
class InitialisationRuntime:
    model: Model
    memory: Memory
    tool_client: ToolClient
    max_attempts: int = 3
    clarifying_questions: dict[str, tuple[Question, Answer] | None] = field(
        default_factory=dict
    )
    tasks: list[TaskSchema] = field(default_factory=list)

    async def run_initial(
        self,
        source_urls: list[str],
        feedback: str,
    ) -> InitialisationResultSchema:
        client = self.model.get_agent_client()
        context = await self.build_agent_context(
            source_urls=source_urls,
            feedback=feedback,
        )
        for _ in range(self.max_attempts):
            raw_intent = await client.send(
                    context,
                    INITIALISATION_PROMPT,
                    InitialisationIntentSchema.model_json_schema(),
                )
            
            intent = InitialisationIntentSchema.model_validate_json(
                    raw_intent
                )
        

            self.tasks = [
                task.model_copy(
                    update={
                        "session_id": self.memory.session_id,
                        "status": TaskStatusEnum.PENDING,
                    }
                )
                for task in intent.tasks
            ]
            self.memory.initialise_tasks(
                self.tasks,
                user_intent=intent.user_intent,
                goal=intent.goal,
            )

            return InitialisationResultSchema(
                decision=InitialisationDecisionEnum.ACCEPTED,
                requested_next_state=LoopStateEnum.EXECUTION,
                intent=intent,
            )

    async def submit_answers(
        self, question_answer_pair: list[tuple[Question, Answer]]
    ) -> None:
        for pair in question_answer_pair:
            question_id = pair[0].question_id
            if question_id in self.clarifying_questions:
                self.clarifying_questions[question_id] = pair

    async def fetch_url(self, fetch_url: str) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(fetch_url)
        response.raise_for_status()
        return response.text

    async def build_agent_context(
        self,
        feedback: str,
        source_urls: list[str],
    ) -> str:
        tools = await self.tool_client.list_tools()
        sources: dict[str, str] = {}
        for url in source_urls:
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
        else:
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
