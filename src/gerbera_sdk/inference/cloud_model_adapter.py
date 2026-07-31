import base64
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import cv2
import requests

from gerbera_sdk.models.hardware.camera import Frame


class ModelProviderEnum(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


@dataclass
class CloudModelAdapter(ABC):
    api_key: str
    model: str
    max_tokens: int = 1024
    timeout_seconds: float = 120.0

    @staticmethod
    def _frame_to_base64(frame: Frame) -> str:
        success, encoded = cv2.imencode(
            ".jpg",
            frame.image,
            [cv2.IMWRITE_JPEG_QUALITY, 90],
        )
        if not success:
            raise RuntimeError("Could not encode camera frame")

        return base64.b64encode(encoded.tobytes()).decode("ascii")

    @abstractmethod
    def convert_to_valid_input(self, frame: Frame) -> dict[str, object]:
        pass

    @abstractmethod
    def predict(
        self,
        model_input: object,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object],
    ) -> dict[str, object]:
        pass

    @staticmethod
    def _parse_json_output(output_text: str) -> dict[str, object]:
        output = json.loads(output_text)
        if not isinstance(output, dict):
            raise RuntimeError(
                "Vision language model output must be a JSON object"
            )
        return output


class AnthropicCloudModelAdapter(CloudModelAdapter):
    def convert_to_valid_input(self, frame: Frame) -> dict[str, object]:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": self._frame_to_base64(frame),
            },
        }

    def predict(
        self,
        model_input: object,
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
                            model_input,
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


class OpenAICloudModelAdapter(CloudModelAdapter):
    def convert_to_valid_input(self, frame: Frame) -> dict[str, object]:
        image_data = self._frame_to_base64(frame)
        return {
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{image_data}",
        }

    def predict(
        self,
        model_input: object,
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
                            model_input,
                            {"type": "input_text", "text": user_prompt},
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
                    return self._parse_json_output(content["text"])
        raise RuntimeError("OpenAI response did not contain structured output")


class GoogleCloudModelAdapter(CloudModelAdapter):
    def convert_to_valid_input(self, frame: Frame) -> dict[str, object]:
        return {
            "type": "image",
            "data": self._frame_to_base64(frame),
            "mime_type": "image/jpeg",
        }

    def predict(
        self,
        model_input: object,
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
                    model_input,
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


CloudModelAdapterRegistry = {
    ModelProviderEnum.ANTHROPIC: AnthropicCloudModelAdapter,
    ModelProviderEnum.OPENAI: OpenAICloudModelAdapter,
    ModelProviderEnum.GOOGLE: GoogleCloudModelAdapter,
}
