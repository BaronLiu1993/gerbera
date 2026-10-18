from dataclasses import dataclass, field

import httpx
from pydantic import JsonValue


@dataclass
class AnthropicAdapter:
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
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": system_prompt,
                    "messages": user_messages,
                    "output_config": {
                        "format": {"type": "json_schema", "schema": output_schema},
                    },
                },
            )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
