from dataclasses import dataclass

import httpx
from pydantic import JsonValue

from gerbera_harness.models.settings import ModelConnectionSettings, TokenLimitParameter
from gerbera_harness.runtime.contracts import ModelRequest


def chat_completion_body(
    request: ModelRequest,
    settings: ModelConnectionSettings,
    token_limit_parameter: TokenLimitParameter,
) -> dict:
    body = {
        "model": settings.model,
        "stream": False,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            *request.messages,
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "node_response", "schema": request.output_schema},
        },
    }
    if settings.maximum_tokens is not None:
        body[token_limit_parameter] = settings.maximum_tokens
    return body


async def send_chat_completion(settings: ModelConnectionSettings, body: dict) -> dict:
    headers = {}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
        response = await client.post(
            settings.endpoint.rstrip("/") + "/chat/completions",
            headers=headers,
            json=body,
        )
    response.raise_for_status()
    return response.json()


@dataclass(frozen=True)
class OpenAICompatibleAdapter:
    settings: ModelConnectionSettings
    token_limit_parameter: TokenLimitParameter = "max_tokens"

    async def send(
        self,
        messages: list[dict[str, str]],
        prompt: str,
        schema: dict[str, JsonValue],
    ) -> str:
        request = ModelRequest(prompt, tuple(messages), schema)
        response = await send_chat_completion(self.settings, self.request_body(request))
        return self.response_content(response)

    def request_body(self, request: ModelRequest) -> dict:
        return chat_completion_body(request, self.settings, self.token_limit_parameter)

    @staticmethod
    def response_content(response: dict) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Model response contains no completion choices")
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Model response exceeded the configured token limit")
        message = choice.get("message", {})
        if message.get("refusal"):
            raise ValueError("Model refused the structured-output request")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model response contains no structured-output content")
        return content
