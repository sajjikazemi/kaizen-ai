import sys
from pathlib import Path

import pytest

from kaizen.config import McpServerConfig
from kaizen.mcp_client import call_tool

_ECHO_SERVER = str(Path(__file__).parent / "fixtures" / "echo_mcp_server.py")


def _server() -> McpServerConfig:
    # Real subprocess over stdio, not mocked - exercises the actual MCP
    # protocol round-trip.
    return McpServerConfig(command=sys.executable, args=[_ECHO_SERVER])


@pytest.mark.asyncio
async def test_call_tool_success():
    outcome = await call_tool(_server(), "echo", {"text": "hello world"})
    assert outcome.is_error is False
    assert outcome.text == "hello world"


@pytest.mark.asyncio
async def test_call_tool_reports_tool_error():
    outcome = await call_tool(_server(), "boom", {"message": "kaboom"})
    assert outcome.is_error is True
    assert "kaboom" in outcome.text
