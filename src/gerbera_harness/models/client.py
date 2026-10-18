from dataclasses import dataclass
import json

from pydantic import JsonValue

from gerbera_harness.models.adapters.base import StructuredOutputAdapter
from gerbera_harness.runtime.contracts import ModelRequest
from gerbera_harness.runtime.state_machine.bindings import validate_document


@dataclass(frozen=True)
class StructuredModelClient:
    adapter: StructuredOutputAdapter

    async def complete(self, request: ModelRequest) -> JsonValue:
        response = await self.adapter.send(
            list(request.messages), request.system_prompt, request.output_schema,
        )
        payload = json.loads(response)
        validate_document(payload, request.output_schema)
        return payload
