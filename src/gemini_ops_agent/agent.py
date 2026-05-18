"""ADK Gemini agent wired to the Dynatrace MCP server.

The McpToolset connection params point at our local stub server by default
(`gemini_ops_agent.mcp_stub`). To target a real Dynatrace tenant, swap to
the official server:

    StdioServerParameters(
        command="npx",
        args=["-y", "@dynatrace-oss/dynatrace-mcp-server"],
        env={
            "DT_ENVIRONMENT_URL": "https://abc.live.dynatrace.com",
            "DT_PLATFORM_TOKEN": "dt0c01.XXX",
        },
    )
"""

from __future__ import annotations

import os
import sys
from typing import Any


# Imports are wrapped so the module is import-able even when google-adk is
# missing (useful for the test suite + dashboard preview).
try:
    from google.adk.agents import LlmAgent
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters
    _ADK_AVAILABLE = True
except ImportError:  # pragma: no cover - optional at import time
    _ADK_AVAILABLE = False


SYSTEM_PROMPT = """\
You are an SRE investigator. The user describes a production symptom and you
diagnose root cause using the Dynatrace tools you have available.

Workflow you should follow:
1. Call `list_problems` to see what Davis AI has already detected.
2. If a problem matches the symptom, call `execute_dql` to pull the underlying
   metrics or logs that explain it.
3. If you need to translate the user's question into DQL, use
   `generate_dql_from_natural_language` first.
4. Always cite specific service names, timestamps, and numbers from the tool
   output in your answer. Don't make numbers up.

Final answer format:
- One-line summary of the root cause.
- 2-4 bullets with the supporting evidence and the DQL or problem ID you used.
- One actionable next step the on-call should take.
"""


def _dynatrace_toolset(stub: bool = True) -> Any:
    """Return an McpToolset bound to either the local stub server (default)
    or the real Dynatrace MCP server when stub=False and credentials are set."""
    if not _ADK_AVAILABLE:
        raise ImportError(
            "google-adk and mcp must be installed: pip install google-adk mcp"
        )

    if stub:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "gemini_ops_agent.mcp_stub"],
            env={
                **os.environ,
                "PYTHONUNBUFFERED": "1",
            },
        )
    else:
        params = StdioServerParameters(
            command="npx",
            args=["-y", "@dynatrace-oss/dynatrace-mcp-server"],
            env={
                **os.environ,
                "DT_ENVIRONMENT_URL": os.environ["DT_ENVIRONMENT_URL"],
                "DT_PLATFORM_TOKEN": os.environ["DT_PLATFORM_TOKEN"],
            },
        )
    return McpToolset(connection_params=StdioConnectionParams(server_params=params))


def build_agent(model: str = "gemini-2.5-flash", stub: bool = True) -> Any:
    """Construct the LlmAgent. Returns None if ADK is unavailable in this
    environment, which keeps imports working for the tests and dashboard
    preview that don't require Vertex AI."""
    if not _ADK_AVAILABLE:
        return None
    return LlmAgent(
        model=model,
        name="gemini_ops_agent",
        instruction=SYSTEM_PROMPT,
        tools=[_dynatrace_toolset(stub=stub)],
    )
