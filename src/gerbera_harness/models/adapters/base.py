from typing import Protocol

from pydantic import JsonValue


class StructuredOutputAdapter(Protocol):
    async def send(
        self,
        messages: list[dict[str, str]],
        prompt: str,
        schema: dict[str, JsonValue],
    ) -> str: ...
