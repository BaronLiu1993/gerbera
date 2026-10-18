from collections.abc import Callable
import os

from gerbera_harness.configuration import ModelSettings
from gerbera_harness.models.adapters.anthropic import AnthropicAdapter
from gerbera_harness.models.adapters.base import StructuredOutputAdapter
from gerbera_harness.models.adapters.google import GoogleAdapter
from gerbera_harness.models.adapters.ollama import OllamaAdapter
from gerbera_harness.models.adapters.openai import OpenAIAdapter
from gerbera_harness.models.adapters.openai_compatible import OpenAICompatibleAdapter
from gerbera_harness.models.adapters.openrouter import OpenRouterAdapter
from gerbera_harness.models.client import StructuredModelClient
from gerbera_harness.models.settings import ModelConnectionSettings, TokenLimitParameter
from gerbera_harness.runtime.contracts import ModelClient


ModelClientFactory = Callable[[ModelSettings], ModelClient]


class ModelClientRegistry:
    def __init__(self) -> None:
        self.factories: dict[tuple[str, str], ModelClientFactory] = {}

    def register(self, key: tuple[str, str], factory: ModelClientFactory) -> None:
        if key in self.factories:
            raise ValueError(f"Model provider already registered: {key}")
        self.factories[key] = factory

    def build(self, settings: ModelSettings) -> ModelClient:
        key = (settings.type, settings.provider)
        if key not in self.factories:
            raise ValueError(f"Unknown model provider: {key}")
        return self.factories[key](settings)


def hosted_factory(adapter_type: Callable[..., StructuredOutputAdapter]) -> ModelClientFactory:
    def build(settings: ModelSettings) -> ModelClient:
        return StructuredModelClient(adapter_type(
            api_key=os.environ[settings.api_key_env],
            model=settings.name,
            max_tokens=settings.maximum_tokens,
            timeout_seconds=settings.timeout_seconds,
        ))
    return build


def compatible_factory(
    endpoint: str | None,
    adapter_type: type[OpenAICompatibleAdapter] = OpenAICompatibleAdapter,
    token_limit_parameter: TokenLimitParameter = "max_tokens",
) -> ModelClientFactory:
    def build(settings: ModelSettings) -> ModelClient:
        configured_endpoint = settings.endpoint or endpoint
        if not configured_endpoint:
            raise ValueError("Custom OpenAI-compatible providers require an endpoint")
        api_key = None
        if settings.type == "api" or "api_key_env" in settings.model_fields_set:
            api_key = os.environ.get(settings.api_key_env)
        if settings.type == "api" and not api_key:
            raise ValueError(f"Set {settings.api_key_env} for provider {settings.provider}")
        adapter = adapter_type(
            ModelConnectionSettings(
                model=settings.name,
                endpoint=configured_endpoint,
                timeout_seconds=settings.timeout_seconds,
                api_key=api_key,
                maximum_tokens=settings.maximum_tokens,
            ),
            token_limit_parameter=settings.token_limit_parameter or token_limit_parameter,
        )
        return StructuredModelClient(adapter)
    return build


def ollama_factory(settings: ModelSettings) -> ModelClient:
    connection = ModelConnectionSettings(
        model=settings.name,
        endpoint=settings.endpoint or "http://localhost:11434",
        timeout_seconds=settings.timeout_seconds,
    )
    return StructuredModelClient(OllamaAdapter(connection))


def default_model_registry() -> ModelClientRegistry:
    registry = ModelClientRegistry()
    registry.register(("api", "openai"), hosted_factory(OpenAIAdapter))
    registry.register(("api", "anthropic"), hosted_factory(AnthropicAdapter))
    registry.register(("api", "google"), hosted_factory(GoogleAdapter))
    registry.register(("api", "groq"), compatible_factory(
        "https://api.groq.com/openai/v1", token_limit_parameter="max_completion_tokens",
    ))
    registry.register(("api", "mistral"), compatible_factory("https://api.mistral.ai/v1"))
    registry.register(("api", "openrouter"), compatible_factory(
        "https://openrouter.ai/api/v1", OpenRouterAdapter,
    ))
    registry.register(("api", "xai"), compatible_factory("https://api.x.ai/v1"))
    registry.register(("api", "openai_compatible"), compatible_factory(None))
    registry.register(("local", "ollama"), ollama_factory)
    registry.register(("local", "openai_compatible"), compatible_factory(
        "http://localhost:8080/v1",
    ))
    return registry
