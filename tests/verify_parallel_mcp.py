#!/usr/bin/env python3
"""Verify Parallel Search MCP works in this repo via the gatekeeper wiring.

Proves:
  1. ADK can open a Streamable HTTP session to Parallel MCP
  2. MCP tool discovery returns web_search / web_fetch
  3. An ADK agent can call Parallel web_search and get real results

Does NOT depend on the Business Research Specialist.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

DEFAULT_QUESTION = "Who owns the Coca-Cola trademark?"


def require_api_key() -> None:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print(
            "Error: GOOGLE_API_KEY or GEMINI_API_KEY required in .env",
            file=sys.stderr,
        )
        sys.exit(1)


async def discover_mcp_tools() -> list[str]:
    """Connect to Parallel MCP and list tools."""
    from gatekeeper.parallel_mcp import (
        PARALLEL_SEARCH_MCP_URL,
        build_parallel_mcp_toolset,
    )

    print(f"Connecting to: {PARALLEL_SEARCH_MCP_URL}")
    toolset = build_parallel_mcp_toolset()
    try:
        tools = await toolset.get_tools()
        return sorted(t.name for t in tools)
    finally:
        await toolset.close()


async def run_search(question: str) -> int:
    from gatekeeper.parallel_search_agent import root_agent

    app_name = "parallel_mcp_verify"
    runner = InMemoryRunner(app_name=app_name, agent=root_agent)
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id="mcp-verify-user",
    )

    user_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=question)],
    )

    print("=" * 72)
    print(f"QUESTION: {question}")
    print("=" * 72)

    saw_tool_call = False
    saw_tool_response = False
    final_text_parts: list[str] = []

    async for event in runner.run_async(
        user_id="mcp-verify-user",
        session_id=session.id,
        new_message=user_message,
    ):
        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            fn_call = getattr(part, "function_call", None)
            if fn_call:
                saw_tool_call = True
                print("\n[TOOL CALL — ADK → Parallel MCP]")
                print(f"  name: {fn_call.name}")
                args = getattr(fn_call, "args", None)
                if args:
                    print(f"  args: {args}")

            fn_resp = getattr(part, "function_response", None)
            if fn_resp:
                saw_tool_response = True
                print("\n[TOOL RESPONSE — Parallel MCP → ADK]")
                print(f"  name: {fn_resp.name}")
                preview = str(getattr(fn_resp, "response", None))
                if len(preview) > 1200:
                    preview = preview[:1200] + "...(truncated)"
                print(f"  response: {preview}")

            text = getattr(part, "text", None)
            if text:
                final_text_parts.append(text)

    print("\n" + "=" * 72)
    print("FINAL ANSWER")
    print("=" * 72)
    print("".join(final_text_parts).strip() or "(no text returned)")

    print("\n" + "=" * 72)
    print("SEARCH VERIFICATION")
    print("=" * 72)
    print(f"ADK called an MCP tool:     {'YES' if saw_tool_call else 'NO'}")
    print(f"Parallel MCP returned data: {'YES' if saw_tool_response else 'NO'}")

    if not saw_tool_call or not saw_tool_response:
        print(
            "\nFailed: Expected web_search/web_fetch via Parallel MCP.",
            file=sys.stderr,
        )
        return 1

    print("\nProof complete: gatekeeper → Parallel Search MCP works.")
    return 0


async def main_async(question: str) -> int:
    print("=" * 72)
    print("1) MCP TOOL DISCOVERY (Parallel hosted server)")
    print("=" * 72)
    names = await discover_mcp_tools()
    print("Discovered MCP tools:")
    for name in names:
        print(f" - {name}")

    expected = {"web_search", "web_fetch"}
    if not expected.issubset(set(names)):
        print(f"FAILED: expected at least {expected}, got {names}")
        return 1
    print("Discovery: PASS\n")

    print("=" * 72)
    print("2) LIVE PARALLEL MCP SEARCH")
    print("=" * 72)
    return await run_search(question)


def main() -> int:
    require_api_key()
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION
    return asyncio.run(main_async(question))


if __name__ == "__main__":
    sys.exit(main())
