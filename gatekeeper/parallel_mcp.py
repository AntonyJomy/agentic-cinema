"""
gatekeeper/parallel_mcp.py

Shared Parallel Search MCP wiring for all research specialists.

Parallel hosts the MCP server at https://search.parallel.ai/mcp
(Streamable HTTP). This module is the ADK client side — there is no
local Parallel MCP process to start.

Ported from the working adk-parallel-mcp integration.

Docs:
- https://google.github.io/adk-docs/tools-custom/mcp-tools/
- https://docs.parallel.ai/integrations/mcp/search-mcp
- https://docs.parallel.ai/integrations/mcp/programmatic-use
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import List
from typing import Optional

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)

# Parallel Search MCP — hosted remote server (Streamable HTTP).
PARALLEL_SEARCH_MCP_URL = "https://search.parallel.ai/mcp"

logger = logging.getLogger("agentic_cinema.parallel_mcp")


def _connection_params() -> StreamableHTTPConnectionParams:
    connection_params: dict = {"url": PARALLEL_SEARCH_MCP_URL}

    parallel_api_key = os.getenv("PARALLEL_API_KEY", "").strip()
    if parallel_api_key:
        connection_params["headers"] = {
            "Authorization": f"Bearer {parallel_api_key}",
        }

    return StreamableHTTPConnectionParams(**connection_params)


def _build_raw_parallel_mcp_toolset() -> McpToolset:
    """Create a low-level ADK McpToolset connected to Parallel Search MCP."""
    return McpToolset(connection_params=_connection_params())


class IsolatedParallelMcpToolset(BaseToolset):
    """Fresh Parallel MCP session pool for each tools listing.

    Specialist agents run concurrently and share one agent graph. A single
    shared ``McpToolset`` can race under asyncio.gather, so the model only
    receives ``set_model_response`` while instructions still tell it to call
    ``web_search`` — which then fails with "Tool 'web_search' not found".
    """

    def __init__(self) -> None:
        super().__init__()
        # Avoid cross-talk between concurrent invocations that share this
        # toolset instance on a specialist LoopAgent.
        self._use_invocation_cache = False
        self._lock = asyncio.Lock()
        self._keepalive: List[McpToolset] = []

    async def get_tools(
        self,
        readonly_context: Optional[ReadonlyContext] = None,
    ) -> List[BaseTool]:
        try:
            return await self._get_tools_inner(readonly_context)
        except Exception:
            logger.warning(
                "Parallel MCP unavailable; continuing without web_search tools",
                exc_info=True,
            )
            return []

    async def _get_tools_inner(
        self,
        readonly_context: Optional[ReadonlyContext] = None,
    ) -> List[BaseTool]:
        inner = _build_raw_parallel_mcp_toolset()
        async with self._lock:
            self._keepalive.append(inner)
            while len(self._keepalive) > 32:
                old = self._keepalive.pop(0)
                try:
                    await old.close()
                except Exception:
                    logger.debug("Failed closing old Parallel MCP toolset", exc_info=True)

        tools = await inner.get_tools(readonly_context)
        if not any(tool.name == "web_search" for tool in tools):
            logger.warning(
                "Parallel MCP tool listing did not include web_search; got: %s",
                [tool.name for tool in tools],
            )
        return tools

    async def close(self) -> None:
        async with self._lock:
            pending = list(self._keepalive)
            self._keepalive.clear()
        for inner in pending:
            try:
                await inner.close()
            except Exception:
                logger.debug("Failed closing Parallel MCP toolset", exc_info=True)


def build_parallel_mcp_toolset() -> BaseToolset:
    """Create an ADK toolset connected to Parallel Search MCP.

    Auth is optional for Search MCP. When PARALLEL_API_KEY is set, it is
    sent as a Bearer token for higher rate limits.

    Returns an isolated wrapper so concurrent specialist runs do not share
    one MCP session pool.
    """
    return IsolatedParallelMcpToolset()
