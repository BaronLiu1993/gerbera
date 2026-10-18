from dataclasses import dataclass, field

import httpx
from pydantic import JsonValue

from gerbera_harness.models.adapters.openai_compatible import (
    chat_completion_body,
    send_chat_completion,
)
from gerbera_harness.models.settings import ModelConnectionSettings
from gerbera_harness.runtime.contracts import ModelRequest


@dataclass
class OpenAIAdapter:
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
        settings = ModelConnectionSettings(
            model=self.model,
            endpoint="https://api.openai.com/v1",
            timeout_seconds=self.timeout_seconds,
            api_key=self.api_key,
            maximum_tokens=self.max_tokens,
        )
        request = ModelRequest(system_prompt, tuple(user_messages), output_schema)
        body = chat_completion_body(request, settings, "max_completion_tokens")
        body["response_format"]["json_schema"].update(name="state_response", strict=True)
        try:
            response = await send_chat_completion(settings, body)
        except httpx.HTTPStatusError as error:
            raise httpx.HTTPStatusError(
                f"{error}\nOpenAI response: {error.response.text}",
                request=error.request,
                response=error.response,
            ) from error
        return self.response_content(response)

    @staticmethod
    def response_content(payload: dict) -> str:
        choice = payload["choices"][0]
        content = choice["message"]["content"]
        if content:
            return content
        usage = payload.get("usage", {})
        raise RuntimeError(
            "OpenAI returned empty content: "
            f"finish_reason={choice.get('finish_reason')!r}, "
            f"completion_tokens={usage.get('completion_tokens')!r}, "
            f"prompt_tokens={usage.get('prompt_tokens')!r}"
        )
