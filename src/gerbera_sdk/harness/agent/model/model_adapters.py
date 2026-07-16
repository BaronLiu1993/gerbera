from dataclasses import dataclass
import httpx


@dataclass
class AnthropicAdapter:
    api_key: str
    model: str
    max_tokens: int

    def send(self, messages: list[dict]) -> str:
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
                "messages": messages,
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


@dataclass
class OpenAIAdapter:
    api_key: str
    model: str
    max_tokens: int

    def send(self, messages: list[dict]) -> str:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


@dataclass
class GeminiAdapter:
    api_key: str
    model: str
    max_tokens: int

    def send(self, messages: list[dict]) -> str:
        resp = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": self.api_key,
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "config": {"max_output_tokens": self.max_tokens},
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
