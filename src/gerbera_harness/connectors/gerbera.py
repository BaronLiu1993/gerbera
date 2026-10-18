from dataclasses import dataclass
import json

from fastmcp import Client
from pydantic import JsonValue
from gerbera_protocol import RuntimeManifest

from gerbera_harness.connectors.urls import require_remote_url
from gerbera_harness.runtime.contracts import ResourceSource, ToolSource
from gerbera_harness.runtime.state_machine.bindings import enforce_json_limit
from gerbera_harness.tools.sources import McpToolSource


@dataclass(frozen=True)
class McpResourceSource:
    url: str

    async def read_resource(self, uri: str) -> JsonValue:
        async with Client(require_remote_url(self.url)) as client:
            contents = await client.read_resource(uri)
        text = "".join(item.text for item in contents if hasattr(item, "text"))
        result = json.loads(text)
        enforce_json_limit(result, 64_000)
        return result


@dataclass(frozen=True)
class GerberaSdkConnector:
    mcp_url: str

    @property
    def tools(self) -> ToolSource:
        return McpToolSource(self.mcp_url)

    @property
    def resources(self) -> ResourceSource:
        return McpResourceSource(self.mcp_url)

    async def connect(self) -> RuntimeManifest:
        manifest = await self.resources.read_resource("gerbera://manifest")
        result = RuntimeManifest.model_validate(manifest)
        await self.tools.list_tools()
        return result

    async def health(self) -> JsonValue:
        return await self.tools.call_tool("get_event_listener_health", {})
