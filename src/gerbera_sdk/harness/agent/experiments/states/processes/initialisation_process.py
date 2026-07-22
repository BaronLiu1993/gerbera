import httpx

from gerbera_sdk.harness.agent.model.mcp_client import MCPClient

class InitialisationLoop:
    urls: list[str]
    system_prompt: str

    def generate_agent_context()

    def fetch_url(self, fetch_url: str) -> str:
        resp = httpx.get(fetch_url, timeout=10.0)
        resp.raise_for_status()
        return resp.text

    async def inspect_hardware(self, client: MCPClient) -> list[dict]:
        tools = await client.list_tools()
        return [
            {"name": t.name, "description": t.description, "schema": t.inputSchema}
            for t in tools
        ]

    async def run(self, user_prompt):
        hardware_setup = await self.inspect_hardware()
        self.messages.append({"role": "system", "content": self.system_prompt})
        self.messages.append({"role": "user", "content": self.user_prompt})
        self.messages.append({"role": "assistant", "content": hardware_setup})
        urls = self.parse_urls(user_prompt)

        for url in urls:
            url_content = self.fetch_url(url)
            self.message.append({"role": "assistant", "content": url_content})
        return self.messages
        

