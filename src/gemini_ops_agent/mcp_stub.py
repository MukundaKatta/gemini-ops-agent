"""Stub Dynatrace MCP server.

Exposes the same tool names as the official dynatrace-oss/dynatrace-mcp
server (list_problems, execute_dql, find_entity_by_name, etc.) but returns
canned realistic responses instead of hitting a live Dynatrace tenant.

Run with: python -m gemini_ops_agent.mcp_stub

The agent connects to this via stdio. Drop in the real Dynatrace MCP server
in production by switching the StdioServerParameters command from this
module to the official npm package.
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# ---------------------------------------------------------------------------
# Canned production data. Reviewers can read this file to verify what the
# agent sees during the demo.
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


@dataclass
class Problem:
    id: str
    title: str
    severity: str
    impacted_entities: list[str]
    started_at: str
    root_cause_summary: str


CANNED_PROBLEMS: list[Problem] = [
    Problem(
        id="P-2026-0517-001",
        title="High latency on checkout-api after 14:32 UTC deploy",
        severity="HIGH",
        impacted_entities=["checkout-api", "payment-svc"],
        started_at=(NOW - timedelta(minutes=23)).isoformat(),
        root_cause_summary=(
            "p95 latency on checkout-api jumped from 220ms to 1.8s starting at "
            "14:32 UTC, correlated with deployment of checkout-api v4.7.1. "
            "DB connection pool wait time increased 9x in the same window."
        ),
    ),
    Problem(
        id="P-2026-0517-002",
        title="Memory leak in recommendation-svc Pod",
        severity="MEDIUM",
        impacted_entities=["recommendation-svc"],
        started_at=(NOW - timedelta(hours=4)).isoformat(),
        root_cause_summary=(
            "Heap usage climbing 12 MB/hour on recommendation-svc; OOM expected "
            "in ~6 hours at current rate. Coincides with onboarding of new "
            "product-catalog feed earlier today."
        ),
    ),
]


def list_problems_response() -> dict[str, Any]:
    return {"problems": [asdict(p) for p in CANNED_PROBLEMS]}


def find_entity_response(name: str) -> dict[str, Any]:
    entities = {
        "checkout-api": "SERVICE-1A2B3C4D5E6F7G8H",
        "payment-svc": "SERVICE-9I8H7G6F5E4D3C2B",
        "recommendation-svc": "SERVICE-ZZ11AA22BB33CC44",
    }
    return {"entity_id": entities.get(name.lower()), "name": name}


def generate_dql_response(question: str) -> dict[str, Any]:
    if "latency" in question.lower():
        dql = (
            "fetch logs, scanLimitGBytes:1\n"
            "| filter service == \"checkout-api\"\n"
            "| summarize p95 = percentile(duration_ms, 95) by bin(timestamp, 1m)\n"
            "| sort timestamp desc\n"
            "| limit 30"
        )
    else:
        dql = "fetch events | filter event.kind == \"DEPLOYMENT\" | sort timestamp desc | limit 20"
    return {"dql": dql}


def _dql_response(query: str) -> dict[str, Any]:
    """Return a canned response for a few representative DQL queries."""
    q = query.lower()
    if "latency" in q and "checkout" in q:
        return {
            "records": [
                {
                    "timestamp": (NOW - timedelta(minutes=i)).isoformat(),
                    "service": "checkout-api",
                    "p95_ms": round(220 + (1800 - 220) * (1 if i < 23 else 0) + random.uniform(-20, 20), 1),
                    "p50_ms": round(110 + (600 - 110) * (1 if i < 23 else 0), 1),
                    "rps": round(140 + random.uniform(-10, 10), 1),
                }
                for i in range(0, 30, 2)
            ],
        }
    if "error" in q or "exception" in q:
        return {
            "records": [
                {
                    "timestamp": (NOW - timedelta(minutes=i)).isoformat(),
                    "service": "checkout-api",
                    "level": "ERROR",
                    "message": (
                        "java.sql.SQLTransientConnectionException: HikariPool-1 "
                        "Connection is not available, request timed out after 30000ms"
                    ),
                    "count": random.randint(8, 35),
                }
                for i in range(0, 20, 3)
            ],
        }
    return {
        "records": [
            {"note": f"stub-dynatrace-mcp received DQL: {query[:200]}"},
        ],
    }


def _make_server() -> Server:
    server = Server("dynatrace-stub")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="list_problems",
                description=(
                    "List currently open problems detected by Dynatrace's Davis AI "
                    "across the monitored environment."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "max_age_hours": {
                            "type": "number",
                            "description": "Only return problems detected in the last N hours.",
                            "default": 24,
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="execute_dql",
                description=(
                    "Run a Dynatrace Query Language (DQL) statement against Grail. "
                    "Returns up to 1000 records."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A DQL query, e.g. `fetch logs | filter ...`",
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="find_entity_by_name",
                description=(
                    "Resolve a service or host name to a Dynatrace monitored "
                    "entity ID."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="generate_dql_from_natural_language",
                description=(
                    "Convert an English description of what you want to know into "
                    "a runnable DQL query."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                    },
                    "required": ["question"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "list_problems":
            payload = list_problems_response()
        elif name == "execute_dql":
            payload = _dql_response(arguments.get("query", ""))
        elif name == "find_entity_by_name":
            payload = find_entity_response(arguments.get("name", ""))
        elif name == "generate_dql_from_natural_language":
            payload = generate_dql_response(arguments.get("question", ""))
        else:
            payload = {"error": f"unknown tool {name!r}"}

        return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]

    return server


async def _main() -> None:
    server = _make_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
