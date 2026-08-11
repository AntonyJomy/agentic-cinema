"""
agents/parallel_mcp.py

Compatibility re-export. Prefer importing from gatekeeper.parallel_mcp —
that is the shared MCP wiring used by specialists.
"""
from gatekeeper.parallel_mcp import (  # noqa: F401
    PARALLEL_SEARCH_MCP_URL,
    build_parallel_mcp_toolset,
)
