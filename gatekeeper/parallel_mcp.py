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

import os

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)

# Parallel Search MCP — hosted remote server (Streamable HTTP).
PARALLEL_SEARCH_MCP_URL = "https://search.parallel.ai/mcp"


def build_parallel_mcp_toolset() -> McpToolset:
    """Create an ADK McpToolset connected to Parallel Search MCP.

    Auth is optional for Search MCP. When PARALLEL_API_KEY is set, it is
    sent as a Bearer token for higher rate limits.
    """
    connection_params: dict = {"url": PARALLEL_SEARCH_MCP_URL}

    parallel_api_key = os.getenv("PARALLEL_API_KEY", "").strip()
    if parallel_api_key:
        connection_params["headers"] = {
            "Authorization": f"Bearer {parallel_api_key}",
        }

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(**connection_params),
    )
