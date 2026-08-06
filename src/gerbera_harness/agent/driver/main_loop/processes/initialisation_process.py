import asyncio
from dataclasses import dataclass, field
import json
import httpx

from gerbera_harness.agent.model.mcp_client import MCPClient

# Deterministic Scripts for Agents
@dataclass
class InitialisationProcess:
    mcp_url: str
    urls: list[str] = field(default_factory=list)
    available_tool_names: frozenset[str] = field(
        default_factory=frozenset,
        init=False,
    )


    def generate_agent_context(
        self,
        user_prompt: str, 
        hardware_tools: list[dict],
        sources: dict[str, str],
        event_catalog: dict | None = None,
    ) -> str:
        sections = [
            "# Experiment Context",
            "## Objective",
            user_prompt.strip(),
            "## Available Rule Events",
            (
                json.dumps(event_catalog, indent=2)
                if event_catalog
                else "No rule events were provided."
            ),
            "## Available Hardware Tools",
        ]

        if hardware_tools:
            for tool in hardware_tools:
                sections.extend(
                    [
                        f"### {tool['name']}",
                        tool.get("description") or "No description provided.",
                        "```json",
                        json.dumps(tool.get("schema", {}), indent=2),
                        "```",
                    ]
                )
        else:
            raise RuntimeError("Failed to Run: No Hardware Tools Detected")

        sections.append("## Research Sources")
        if sources:
            for url, content in sources.items():
                sections.extend([f"### {url}", content.strip()])
        else:
            sections.append("No research sources were provided.")
        return "\n\n".join(sections)

    async def fetch_url(self, fetch_url: str) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(fetch_url)
        resp.raise_for_status()
        return resp.text

    async def inspect_hardware(self, client: MCPClient) -> list[dict]:
        tools = await client.list_tools()

        return [
            {"name": t.name, "description": t.description, "schema": t.inputSchema}
            for t in tools
        ]
    
    async def run(self, user_prompt: str) -> str:
        async with MCPClient(self.mcp_url) as client:
            hardware_tools = await self.inspect_hardware(client)
            available_tool_names = frozenset(
                tool["name"] for tool in hardware_tools
            )
            event_catalog = {}
            if "list_rule_events" in available_tool_names:
                event_catalog = await client.call_tool(
                    "list_rule_events",
                    {},
                    available_tool_names,
                    structured=True,
                )

        self.available_tool_names = available_tool_names

        source_contents = await asyncio.gather(
            *(self.fetch_url(url) for url in self.urls)
        )
        sources = dict(zip(self.urls, source_contents, strict=True))
        return self.generate_agent_context(
            user_prompt=user_prompt,
            hardware_tools=hardware_tools,
            sources=sources,
            event_catalog=event_catalog,
        )
