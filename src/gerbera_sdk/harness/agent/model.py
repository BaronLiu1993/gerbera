from dataclasses import dataclass, field
from enum import Enum
import uuid
from model_adapters import AnthropicAdapter, OpenAIAdapter, GeminiAdapter


class ModelProviderEnum(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


MODEL_MAP = {
    ModelProviderEnum.ANTHROPIC: AnthropicAdapter,
    ModelProviderEnum.OPENAI: OpenAIAdapter,
    ModelProviderEnum.GEMINI: GeminiAdapter,
}


@dataclass
class AgentClient:
    model_provider: ModelProviderEnum
    model: str
    api_key: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def create_agent_client(self):
        adapter_cls = MODEL_MAP.get(self.model_provider)
        if adapter_cls is None:
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
        return adapter_cls(api_key=self.api_key, model=self.model)