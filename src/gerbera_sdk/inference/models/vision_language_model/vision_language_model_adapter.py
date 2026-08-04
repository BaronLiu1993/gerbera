import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeAlias

import requests

from gerbera_sdk.inference.model_types import VisionLanguageModelProviderEnum


@dataclass
class VisionLanguageModelAdapter(ABC):
    api_key: str
    model: str
    max_tokens: int = 1024
    timeout_seconds: float = 120.0

    @staticmethod
    def _parse_json_output(output_text: str) -> dict[str, object]:
        output = json.loads(output_text)
        if not isinstance(output, dict):
            raise RuntimeError(
                "Vision language model output must be a JSON object"
            )
        return output

    @abstractmethod
    def convert_to_valid_input(
        self,
        frame: str,
    ) -> dict[str, object]:
        pass

    @abstractmethod
    def predict(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object],
    ) -> dict[str, object]:
        pass


class AnthropicVisionLanguageModelAdapter(VisionLanguageModelAdapter):
    def convert_to_valid_input(
        self,
        frame: str,
    ) -> dict[str, object]:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": frame,
            },
        }

    def predict(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object],
    ) -> dict[str, object]:
        response = requests.post(
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
                "output_config": {
                    "format": {
                        "type": "json_schema",
                        "schema": output_schema,
                    }
                },
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            *model_input,
                            {"type": "text", "text": user_prompt},
                        ],
                    }
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return self._parse_json_output(payload["content"][0]["text"])


class OpenAIVisionLanguageModelAdapter(VisionLanguageModelAdapter):
    def convert_to_valid_input(
        self,
        frame: str,
    ) -> dict[str, object]:
        return {
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{frame}",
        }

    def predict(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object],
    ) -> dict[str, object]:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": system_prompt,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "vision_language_model_frame_environment",
                        "schema": output_schema,
                        "strict": True,
                    }
                },
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_prompt},
                            *model_input,
                        ],
                    }
                ],
            },
            timeout=self.timeout_seconds,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise requests.HTTPError(
                f"{exc}\nOpenAI response: {response.text}",
                request=exc.request,
                response=exc.response,
            ) from exc
        payload = response.json()
        for output in payload.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    return self._parse_json_output(content["text"])
        raise RuntimeError("OpenAI response did not contain structured output")


class GoogleVisionLanguageModelAdapter(VisionLanguageModelAdapter):
    def convert_to_valid_input(
        self,
        frame: str,
    ) -> dict[str, object]:
        return {
            "type": "image",
            "data": frame,
            "mime_type": "image/jpeg",
        }

    def predict(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object],
    ) -> dict[str, object]:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "system_instruction": system_prompt,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": output_schema,
                },
                "input": [
                    *model_input,
                    {"type": "text", "text": user_prompt},
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        for step in payload.get("steps", []):
            if step.get("type") != "model_output":
                continue
            for content in step.get("content", []):
                if content.get("type") == "text":
                    return self._parse_json_output(content["text"])
        raise RuntimeError("Google response did not contain structured output")


VisionLanguageModelAdapters: TypeAlias = (
    AnthropicVisionLanguageModelAdapter
    | OpenAIVisionLanguageModelAdapter
    | GoogleVisionLanguageModelAdapter
)

VISION_LANGUAGE_MODEL_REGISTRY = {
    VisionLanguageModelProviderEnum.ANTHROPIC: AnthropicVisionLanguageModelAdapter,
    VisionLanguageModelProviderEnum.OPENAI: OpenAIVisionLanguageModelAdapter,
    VisionLanguageModelProviderEnum.GOOGLE: GoogleVisionLanguageModelAdapter,
}
