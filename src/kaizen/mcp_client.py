"""A minimal, direct MCP client for scripted `mcp_tool_call` eval cases.

Deliberately doesn't go through `langchain_mcp_adapters`/an agent: that
path wraps results for LLM consumption (stringified, errors folded into
exceptions or tool-call status) which loses exactly the structured
`isError`/content distinction a deterministic assertion needs. This talks
the MCP stdio protocol directly for one tool call and returns the raw
result.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client

from kaizen.config import McpServerConfig


@dataclass
class ToolCallOutcome:
    is_error: bool
    text: str


def _extract_text(content: list[types.ContentBlock]) -> str:
    return "\n".join(block.text for block in content if isinstance(block, types.TextContent))


async def call_tool(
    server: McpServerConfig, tool: str, arguments: dict, timeout_seconds: int = 300
) -> ToolCallOutcome:
    """Connects to `server` over stdio, calls `tool(**arguments)` once, and
    returns its result. Raises if the server can't be reached/initialized -
    that's a connection failure, distinct from the tool itself reporting
    `isError` (which is a normal, expected outcome this returns, not raises)."""
    params = StdioServerParameters(
        command=server.command, args=server.args, cwd=server.cwd, env=server.env or None
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            tool, arguments, read_timeout_seconds=timedelta(seconds=timeout_seconds)
        )
    return ToolCallOutcome(is_error=result.isError, text=_extract_text(result.content))
