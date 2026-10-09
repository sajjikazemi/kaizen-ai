"""Executes one task_prompt eval case against the target's MCP server.

Isolated in its own module so the Claude Agent SDK import stays lazy/optional
(command-only setups shouldn't need it installed).
"""
from __future__ import annotations

from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalCase


async def run_mcp_task(case: EvalCase, config: KaizenConfig) -> tuple[str, bool, list[str]]:
    """Runs ``case.task_prompt`` through Claude, connected to the target MCP server.

    Returns (full_text_output, success, raw_tool_errors).
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
    )

    if config.mcp_server is None:
        raise ValueError(
            f"Eval case {case.id!r} uses task_prompt but no mcp_server is configured "
            f"in kaizen.yaml for project {config.project_name!r}"
        )

    mcp_servers = {
        "target": {
            "type": "stdio",
            "command": config.mcp_server.command,
            "args": config.mcp_server.args,
            "env": config.mcp_server.env,
        }
    }

    options = ClaudeAgentOptions(
        mcp_servers=mcp_servers,
        cwd=config.mcp_server.cwd or config.repo_path,
        permission_mode="default",  # never auto-accept destructive actions
        max_turns=10,
    )

    text_chunks: list[str] = []
    tool_errors: list[str] = []
    success = False

    async with ClaudeSDKClient(options=options) as client:
        await client.query(case.task_prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                success = not message.is_error
                if message.is_error:
                    tool_errors.append(str(message.result))

    full_text = "\n".join(text_chunks)
    if case.expect_output_contains:
        success = success and all(needle in full_text for needle in case.expect_output_contains)
    return full_text, success, tool_errors
