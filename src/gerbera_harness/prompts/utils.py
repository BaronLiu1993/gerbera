from enum import Enum
from pathlib import Path


PROMPT_DIRECTORY = Path(__file__).resolve().parent


class PromptTypeEnum(str, Enum):
    MAIN = "main"
    SUB = "sub"


def load_prompt(prompt_type: PromptTypeEnum, file_name: str) -> str:
    prompt_path = PROMPT_DIRECTORY / prompt_type.value / file_name
    return prompt_path.read_text().strip()
