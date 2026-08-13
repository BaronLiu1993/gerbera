import asyncio

import httpx
import pytest

from gerbera_harness.infrastructure import llm_adapters as model_adapters
from gerbera_harness.infrastructure.llm_adapters import (
    AnthropicAdapter,
    GoogleAdapter,
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
            GoogleAdapter("key", "gemini", 100),
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

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured_request["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            pass

        async def post(self, url, **kwargs):
            captured_request.update(kwargs["json"])
            return FakeResponse(response_payload)

    monkeypatch.setattr(
        model_adapters.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )
    schema = {
        "type": "object",
        "properties": {"next_state": {"type": "string"}},
        "required": ["next_state"],
        "additionalProperties": False,
    }

    assert asyncio.run(adapter.send([], "state prompt", schema)) == "{}"
    assert schema_from_request(captured_request) is schema
    assert captured_request["timeout"] == 120.0

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

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            pass

        async def post(self, url, **kwargs):
            return response

    monkeypatch.setattr(
        model_adapters.httpx,
        "AsyncClient",
        FakeAsyncClient,
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
        asyncio.run(adapter.send([], "state prompt", schema))


def test_openai_adapter_rejects_empty_content_with_response_details() -> None:
    payload = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {"content": ""},
            }
        ],
        "usage": {
            "completion_tokens": 1000,
            "prompt_tokens": 2000,
        },
    }

    with pytest.raises(
        RuntimeError,
        match="OpenAI returned empty content.*finish_reason='length'",
    ):
        OpenAIAdapter.response_content(payload)


def test_adapter_request_can_be_cancelled(monkeypatch) -> None:
    request_started = asyncio.Event()
    request_cancelled = asyncio.Event()

    class HangingAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            pass

        async def post(self, url, **kwargs):
            request_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                request_cancelled.set()
                raise

    monkeypatch.setattr(
        model_adapters.httpx,
        "AsyncClient",
        HangingAsyncClient,
    )
    adapter = OpenAIAdapter("key", "gpt", 100)

    async def run_request() -> None:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(
                adapter.send([], "state prompt", {}),
                timeout=0.001,
            )

        assert request_started.is_set()
        assert request_cancelled.is_set()

    asyncio.run(run_request())
