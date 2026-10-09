"""Builds a Copilot CLI ``--additional-mcp-config`` payload from a target
project's ``mcp_server`` config block - same schema the CLI already reads
from ``~/.copilot/mcp-config.json`` / ``.mcp.json``.
"""
from __future__ import annotations

from kaizen.config import KaizenConfig


def build_mcp_config(config: KaizenConfig, server_name: str = "target") -> dict | None:
    if config.mcp_server is None:
        return None
    server = config.mcp_server
    entry: dict = {
        "type": "local",
        "command": server.command,
        "args": server.args,
        "env": server.env,
        "tools": ["*"],
    }
    if server.cwd:
        entry["cwd"] = server.cwd
    return {"mcpServers": {server_name: entry}}
