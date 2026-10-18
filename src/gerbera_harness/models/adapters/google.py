from dataclasses import dataclass, field

import httpx
from pydantic import JsonValue


@dataclass
class GoogleAdapter:
    api_key: str = field(repr=False)
    model: str
    max_tokens: int
    timeout_seconds: float = 120.0

    async def send(
        self,
        user_messages: list[dict[str, str]],
        system_prompt: str,
        output_schema: dict[str, JsonValue],
    ) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={
                    "x-goog-api-key": self.api_key,
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "system_prompt": system_prompt,
                    "messages": user_messages,
                    "config": {"max_output_tokens": self.max_tokens},
                    "response_format": {
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": output_schema,
                    },
                },
            )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
