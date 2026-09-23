from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

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

    @staticmethod
    def _raise_for_status(
        response: httpx.Response,
        provider: str,
    ) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise httpx.HTTPStatusError(
                f"{exc}\n{provider} response: {response.text}",
                request=exc.request,
                response=exc.response,
            ) from exc

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

    @abstractmethod
    def analyze_scene(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
    ) -> str:
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
        return self._parse_json_output(
            self._request(
                model_input=model_input,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
            )
        )

    def analyze_scene(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return self._request(model_input, system_prompt, user_prompt)

    def _request(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        body: dict[str, object] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        *model_input,
                        {"type": "text", "text": user_prompt},
                    ],
                }
            ],
        }
        if output_schema is not None:
            body["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": output_schema,
                }
            }

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=self.timeout_seconds,
        )
        self._raise_for_status(response, "Anthropic")
        payload = response.json()
        try:
            text = payload["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "Anthropic response did not contain text content"
            ) from exc
        if not isinstance(text, str):
            raise RuntimeError("Anthropic response text must be a string")
        return text


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
        return self._parse_json_output(
            self._request(
                model_input=model_input,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
            )
        )

    def analyze_scene(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return self._request(model_input, system_prompt, user_prompt)

    def _request(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        body: dict[str, object] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        *model_input,
                    ],
                }
            ],
        }
        if output_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "vision_language_model_frame_environment",
                    "schema": output_schema,
                    "strict": True,
                }
            }

        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self.timeout_seconds,
        )
        self._raise_for_status(response, "OpenAI")
        payload = response.json()
        for output in payload.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str):
                        return text
        raise RuntimeError("OpenAI response did not contain output_text")


class GoogleVisionLanguageModelAdapter(VisionLanguageModelAdapter):
    def convert_to_valid_input(
        self,
        frame: str,
    ) -> dict[str, object]:
        return {
            "inline_data": {
                "mime_type": "image/jpeg",
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
        return self._parse_json_output(
            self._request(
                model_input=model_input,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
            )
        )

    def analyze_scene(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return self._request(model_input, system_prompt, user_prompt)

    def _request(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        body: dict[str, object] = {
            "system_instruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        *model_input,
                        {"text": user_prompt},
                    ],
                }
            ],
        }
        if output_schema is not None:
            body["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseSchema": output_schema,
            }

        response = httpx.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{self.model}:generateContent"
            ),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self.timeout_seconds,
        )
        self._raise_for_status(response, "Google")
        payload = response.json()
        for candidate in payload.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                text = part.get("text")
                if isinstance(text, str):
                    return text
        raise RuntimeError("Google response did not contain candidate text")


VISION_LANGUAGE_MODEL_REGISTRY = {
    VisionLanguageModelProviderEnum.ANTHROPIC: AnthropicVisionLanguageModelAdapter,
    VisionLanguageModelProviderEnum.OPENAI: OpenAIVisionLanguageModelAdapter,
    VisionLanguageModelProviderEnum.GOOGLE: GoogleVisionLanguageModelAdapter,
}
