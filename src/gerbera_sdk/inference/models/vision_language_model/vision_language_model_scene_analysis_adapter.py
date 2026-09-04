from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeAlias

import httpx

from gerbera_sdk.inference.model_types import VisionLanguageModelProviderEnum


@dataclass
class VisionLanguageSceneAnalysisAdapter(ABC):
    api_key: str
    model: str
    max_tokens: int
    timeout_seconds: float

    @abstractmethod
    def convert_to_valid_input(
        self,
        frame: str,
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


class AnthropicVisionLanguageSceneAnalysisAdapter(
    VisionLanguageSceneAnalysisAdapter
):
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

    def analyze_scene(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = httpx.post(
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
        return payload["content"][0]["text"]


class OpenAIVisionLanguageSceneAnalysisAdapter(
    VisionLanguageSceneAnalysisAdapter
):
    def convert_to_valid_input(
        self,
        frame: str,
    ) -> dict[str, object]:
        return {
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{frame}",
        }

    def analyze_scene(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
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
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        for output in payload.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    return content["text"]
        raise RuntimeError("OpenAI response did not contain output_text")


class GoogleVisionLanguageSceneAnalysisAdapter(
    VisionLanguageSceneAnalysisAdapter
):
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

    def analyze_scene(
        self,
        model_input: list[dict[str, object]],
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = httpx.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{self.model}:generateContent"
            ),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
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
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        for candidate in payload.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                text = part.get("text")
                if text is not None:
                    return text
        raise RuntimeError("Google response did not contain candidate text")


VisionLanguageSceneAnalysisAdapters: TypeAlias = (
    AnthropicVisionLanguageSceneAnalysisAdapter
    | OpenAIVisionLanguageSceneAnalysisAdapter
    | GoogleVisionLanguageSceneAnalysisAdapter
)

VISION_LANGUAGE_SCENE_ANALYSIS_REGISTRY = {
    VisionLanguageModelProviderEnum.ANTHROPIC: (
        AnthropicVisionLanguageSceneAnalysisAdapter
    ),
    VisionLanguageModelProviderEnum.OPENAI: OpenAIVisionLanguageSceneAnalysisAdapter,
    VisionLanguageModelProviderEnum.GOOGLE: GoogleVisionLanguageSceneAnalysisAdapter,
}
