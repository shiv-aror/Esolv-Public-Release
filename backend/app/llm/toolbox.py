"""MCP client side: connects the orchestrator to the Canvas + knowledge MCP servers and exposes their tools to the LLM."""
import json
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from ..mcp.canvas_server import mcp as canvas_mcp
from ..mcp.context import current_user_email
from ..mcp.knowledge_server import mcp as knowledge_mcp


class Toolbox:
    """In-process MCP transport (one deployable). The same servers are also mounted over streamable HTTP at /mcp/*."""

    def __init__(self, user_email: str):
        self.user_email = user_email
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tool_server: dict[str, str] = {}
        self._defs: list[dict] = []

    async def __aenter__(self):
        current_user_email.set(self.user_email)
        for label, server in (("knowledge", knowledge_mcp), ("canvas", canvas_mcp)):
            sess = await self._stack.enter_async_context(create_connected_server_and_client_session(server._mcp_server))
            self._sessions[label] = sess
            for t in (await sess.list_tools()).tools:
                self._tool_server[t.name] = label
                self._defs.append({"type": "function", "function": {
                    "name": t.name, "description": t.description or "", "parameters": t.inputSchema}})
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    def openai_tools(self) -> list[dict]:
        return self._defs

    async def call(self, name: str, args: dict) -> dict:
        label = self._tool_server.get(name)
        if not label:
            return {"error": f"Unknown tool {name}"}
        res = await self._sessions[label].call_tool(name, args)
        text = "".join(getattr(c, "text", "") for c in res.content)
        try:
            return json.loads(text)
        except Exception:
            return {"error": text[:300] or "Tool returned no data"} if res.isError else {"text": text}


def toolbox_for(user_email: str) -> Toolbox:
    """Factory seam: swap in a streamable-HTTP client here when the MCP servers move to their own cloud services."""
    return Toolbox(user_email)
