import json
from dataclasses import dataclass, field

import httpx

from gerbera_harness.agent.model.mcp_client import MCPClient
from gerbera_harness.tools.base import ToolSpec


@dataclass
class InitialisationProcess:
    mcp_url: str
    local_tools: tuple[ToolSpec, ...]
    urls: list[str] = field(default_factory=list)

    def generate_agent_context(
        self,
        user_prompt: str,
        hardware_tools: list[dict],
        sources: dict[str, str],
    ) -> str:
        sections = [
            "# Experiment Context",
            "## Objective",
            user_prompt.strip(),
        ]

        sections.append("## Available Hardware Tools")
        for tool in hardware_tools:
            sections.append(f"### {tool['name']}")
            sections.append(tool["description"])
            sections.append("```json")
            sections.append(json.dumps(tool["schema"], indent=2))
            sections.append("```")

        sections.append("## Available Local Tools")
        for tool in self.local_tools:
            sections.append(f"### {tool.name}")
            sections.append(tool.description)
            sections.append("```json")
            sections.append(json.dumps(tool.input_schema, indent=2))
            sections.append("```")

        sections.append("## Research Sources")
        if not sources:
            sections.append("No research sources were provided.")

        for url, content in sources.items():
            sections.append(f"### {url}")
            sections.append(content.strip())

        print(sections)
        return "\n\n".join(sections)

    async def fetch_url(self, fetch_url: str) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(fetch_url)
        response.raise_for_status()
        return response.text

    async def inspect_hardware(self, client: MCPClient) -> list[dict]:
        tools = await client.list_tools()
        hardware_tools: list[dict] = []
        for tool in tools:
            hardware_tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.inputSchema,
                }
            )

        if not hardware_tools:
            raise RuntimeError("No hardware tools were registered")
        return hardware_tools

    async def run(self, user_prompt: str) -> str:
        async with MCPClient(self.mcp_url) as client:
            hardware_tools = await self.inspect_hardware(client)

        sources: dict[str, str] = {}
        for url in self.urls:
            sources[url] = await self.fetch_url(url)

        return self.generate_agent_context(
            user_prompt=user_prompt,
            hardware_tools=hardware_tools,
            sources=sources,
        )
