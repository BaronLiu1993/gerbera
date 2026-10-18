from dataclasses import dataclass

import httpx
from pydantic import JsonValue

from gerbera_harness.models.settings import ModelConnectionSettings


@dataclass(frozen=True)
class OllamaAdapter:
    settings: ModelConnectionSettings

    async def send(
        self,
        messages: list[dict[str, str]],
        prompt: str,
        schema: dict[str, JsonValue],
    ) -> str:
        body = {
            "model": self.settings.model,
            "stream": False,
            "messages": [{"role": "system", "content": prompt}, *messages],
            "format": schema,
        }
        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            response = await client.post(
                self.settings.endpoint.rstrip("/") + "/api/chat", json=body,
            )
        response.raise_for_status()
        return response.json()["message"]["content"]
