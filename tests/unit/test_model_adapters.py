import httpx
import pytest

from gerbera_sdk.harness.agent.model import model_adapters
from gerbera_sdk.harness.agent.model.model_adapters import (
    AnthropicAdapter,
    GeminiAdapter,
    OpenAIAdapter,
)


class FakeResponse:
    def __init__(self, payload: dict, text: str = "") -> None:
        self._payload = payload
        self.text = text

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


def test_openai_adapter_includes_response_body_in_http_errors(
    monkeypatch,
) -> None:
    request = httpx.Request(
        "POST",
        "https://api.openai.com/v1/chat/completions",
    )
    response = httpx.Response(
        400,
        request=request,
        text='{"error":{"message":"Invalid schema"}}',
    )

    monkeypatch.setattr(
        model_adapters.httpx,
        "post",
        lambda *args, **kwargs: response,
    )

    adapter = OpenAIAdapter("key", "gpt", 100)
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    with pytest.raises(
        httpx.HTTPStatusError,
        match="OpenAI response.*Invalid schema",
    ):
        adapter.send([], "state prompt", schema)
