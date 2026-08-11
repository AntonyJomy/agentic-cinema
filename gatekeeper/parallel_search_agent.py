"""
gatekeeper/parallel_search_agent.py

Minimal Google ADK agent that uses Parallel Search MCP only.

Used to prove the shared gatekeeper MCP wiring works independently of
any research specialist (business / character / music).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent

from gatekeeper.parallel_mcp import build_parallel_mcp_toolset

load_dotenv()

if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

root_agent = Agent(
    model="gemini-3.6-flash",
    name="parallel_search_agent",
    description=(
        "Answers factual questions using Parallel's official Search MCP "
        "(web_search / web_fetch)."
    ),
    instruction=(
        "You are a research assistant with access to Parallel Search MCP tools.\n"
        "For any factual question, you MUST call the web_search tool before answering.\n"
        "In your final answer:\n"
        "1. State the answer clearly.\n"
        "2. Include source URLs from the tool results as citations.\n"
        "Do not invent facts that are not supported by the tool output."
    ),
    tools=[build_parallel_mcp_toolset()],
)
