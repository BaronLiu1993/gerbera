from dataclasses import dataclass, field
import uuid
from gerbera_harness.agent.driver.main_loop.schema.utils import StrictSchema


class QuestionSchema(StrictSchema):
    question: str
    options: list[str]


@dataclass
class Question:
    question: str
    options: list[str]
    question_id: str = field(default_factory=lambda: str(uuid.uuid4()))

# This is formed when the user submits an answer.
@dataclass
class Answer:
    question_id: str
    question: str
    answer: str
