"""MCP Client — connect to travel-mcp-server via stdio."""

import json
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import settings

logger = logging.getLogger(__name__)


class TravelMcpClient:
    """Singleton MCP client for the travel tool server."""

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and self._session is not None

    def _resolve_server_args(self) -> list[str]:
        script = settings.mcp_server_script
        p = Path(script)
        if not p.is_absolute():
            backend_dir = Path(__file__).resolve().parents[2]
            repo_root = backend_dir.parent
            for base in (backend_dir, repo_root):
                candidate = (base / script).resolve()
                if candidate.exists():
                    return [str(candidate)]
            return [str((repo_root / script).resolve())]
        return [str(p)]

    def _server_env(self) -> dict[str, str]:
        env = dict(os.environ)
        backend_dir = Path(__file__).resolve().parents[2]
        pythonpath = env.get("PYTHONPATH", "")
        backend_str = str(backend_dir)
        if backend_str not in pythonpath.split(os.pathsep):
            env["PYTHONPATH"] = backend_str + (os.pathsep + pythonpath if pythonpath else "")
        return env

    async def connect(self) -> None:
        if not settings.mcp_enabled:
            logger.info("[MCP] disabled by config")
            return
        if self._connected:
            return
        try:
            server_args = self._resolve_server_args()
            params = StdioServerParameters(
                command=settings.mcp_server_command,
                args=server_args,
                env=self._server_env(),
            )
            self._stack = AsyncExitStack()
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._session = session
            self._connected = True
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            logger.info("[MCP] connected, tools: %s", names)
        except Exception as e:
            logger.warning("[MCP] connect failed, agent will use local tools only: %s", e)
            await self.disconnect()

    async def disconnect(self) -> None:
        self._connected = False
        self._session = None
        if self._stack is not None:
            try:
                await self._stack.aclose()
            except Exception:
                pass
            self._stack = None

    async def list_tools(self) -> list[str]:
        if not self._session:
            return []
        result = await self._session.list_tools()
        return [t.name for t in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._session:
            return {"error": "MCP client not connected"}
        try:
            result = await self._session.call_tool(name, arguments=arguments)
            if result.isError:
                texts = [c.text for c in result.content if hasattr(c, "text")]
                return {"error": " ".join(texts) or "MCP tool error"}
            # Parse structured or text content
            for block in result.content:
                if hasattr(block, "text") and block.text:
                    try:
                        return json.loads(block.text)
                    except json.JSONDecodeError:
                        return {"value": block.text}
            return {"value": str(result.content)}
        except Exception as e:
            return {"error": f"MCP call failed: {e}"}


mcp_client = TravelMcpClient()
