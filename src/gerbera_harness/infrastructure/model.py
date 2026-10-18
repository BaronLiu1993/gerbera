from dataclasses import dataclass, field
import json
import uuid

from gerbera_harness.runtime.contracts import ModelClient, ModelRequest


@dataclass
class Model:
    client: ModelClient
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def get_agent_client(self):
        return self

    async def send(self, messages: list[dict], prompt: str, schema: dict) -> str:
        result = await self.client.complete(ModelRequest(prompt, tuple(messages), schema))
        return json.dumps(result)
