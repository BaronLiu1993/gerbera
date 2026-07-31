import base64
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
    ) -> object:
        pass


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
    ) -> object:
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
        return response.json()


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
    ) -> object:
        response = requests.post(
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
                            model_input,
                            {"type": "input_text", "text": user_prompt},
                        ],
                    }
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


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
    ) -> object:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "system_instruction": system_prompt,
                "input": [
                    model_input,
                    {"type": "text", "text": user_prompt},
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


CloudModelAdapterRegistry = {
    ModelProviderEnum.ANTHROPIC: AnthropicCloudModelAdapter,
    ModelProviderEnum.OPENAI: OpenAICloudModelAdapter,
    ModelProviderEnum.GOOGLE: GoogleCloudModelAdapter,
}
