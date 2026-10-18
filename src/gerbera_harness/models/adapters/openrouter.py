from dataclasses import dataclass

from gerbera_harness.models.adapters.openai_compatible import OpenAICompatibleAdapter
from gerbera_harness.runtime.contracts import ModelRequest


@dataclass(frozen=True)
class OpenRouterAdapter(OpenAICompatibleAdapter):
    def request_body(self, request: ModelRequest) -> dict:
        body = super().request_body(request)
        body["provider"] = {"require_parameters": True}
        return body
