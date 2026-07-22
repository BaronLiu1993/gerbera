import pytest

from gerbera_sdk.harness.agent.model import model_adapters
from gerbera_sdk.harness.agent.model.model_adapters import (
    AnthropicAdapter,
    GeminiAdapter,
    OpenAIAdapter,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


@pytest.mark.parametrize(
    ("adapter", "response_payload", "schema_from_request"),
    [
        (
            AnthropicAdapter("key", "claude", 100),
            {"content": [{"text": "{}"}]},
            lambda request: request["output_config"]["format"]["schema"],
        ),
        (
            OpenAIAdapter("key", "gpt", 100),
            {"choices": [{"message": {"content": "{}"}}]},
            lambda request: request["response_format"]["json_schema"]["schema"],
        ),
        (
            GeminiAdapter("key", "gemini", 100),
            {"content": [{"text": "{}"}]},
            lambda request: request["response_format"]["schema"],
        ),
    ],
)
def test_adapter_uses_native_structured_output_field(
    monkeypatch,
    adapter,
    response_payload: dict,
    schema_from_request,
) -> None:
    captured_request = {}

    def fake_post(url, **kwargs):
        captured_request.update(kwargs["json"])
        return FakeResponse(response_payload)

    monkeypatch.setattr(model_adapters.httpx, "post", fake_post)
    schema = {
        "type": "object",
        "properties": {"next_state": {"type": "string"}},
        "required": ["next_state"],
        "additionalProperties": False,
    }

    assert adapter.send([], "state prompt", schema) == "{}"
    assert schema_from_request(captured_request) is schema

    if isinstance(adapter, OpenAIAdapter):
        assert captured_request["response_format"]["json_schema"]["strict"] is True
