from dataclasses import dataclass, field
from enum import Enum
import uuid

from gerbera_harness.agent.model.model_adapters import (
    AnthropicAdapter,
    GoogleAdapter,
    OpenAIAdapter,
)


class ModelProviderEnum(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


MODEL_MAP = {
    ModelProviderEnum.ANTHROPIC: AnthropicAdapter,
    ModelProviderEnum.OPENAI: OpenAIAdapter,
    ModelProviderEnum.GOOGLE: GoogleAdapter,
}


@dataclass
class Model:
    model_provider: ModelProviderEnum
    model: str
    api_key: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def get_agent_client(self):
        adapter_cls = MODEL_MAP.get(self.model_provider)
        if adapter_cls is None:
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
        return adapter_cls(api_key=self.api_key, model=self.model, max_tokens=8192)
