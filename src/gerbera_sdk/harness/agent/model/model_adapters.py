from dataclasses import dataclass
import httpx


@dataclass
class AnthropicAdapter:
    api_key: str
    model: str
    max_tokens: int
    timeout_seconds: float = 120.0

    def send(
        self,
        user_messages: list[dict],
        system_prompt: str,
        valid_schema: dict,
    ) -> str:
        resp = httpx.post(
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
                    "format": {
                        "type": "json_schema",
                        "schema": valid_schema,
                    }
                },
            },
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


@dataclass
class OpenAIAdapter:
    api_key: str
    model: str
    max_tokens: int
    timeout_seconds: float = 120.0

    def send(
        self,
        user_messages: list[dict],
        system_prompt: str,
        valid_schema: dict,
    ) -> str:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    *user_messages,
                ],
                "max_tokens": self.max_tokens,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "state_response",
                        "strict": True,
                        "schema": valid_schema,
                    },
                },
            },
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


@dataclass
class GeminiAdapter:
    api_key: str
    model: str
    max_tokens: int
    timeout_seconds: float = 120.0

    def send(
        self,
        user_messages: list[dict],
        system_prompt: str,
        valid_schema: dict,
    ) -> str:
        resp = httpx.post(
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
                    "schema": valid_schema,
                },
            },
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
