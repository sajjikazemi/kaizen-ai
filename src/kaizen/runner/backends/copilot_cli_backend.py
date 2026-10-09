"""Runner backend that drives an eval case's `task_prompt` through the
already-authenticated GitHub Copilot CLI instead of a direct LLM provider
API - no separate API key needed. Connects to the target's MCP server via
Copilot CLI's own ``--additional-mcp-config`` flag.
"""
from __future__ import annotations

import uuid

from kaizen.config import KaizenConfig
from kaizen.copilot_cli.mcp_config import build_mcp_config
from kaizen.copilot_cli.run import run_copilot_prompt_async
from kaizen.evals.schema import EvalCase


async def run_mcp_task(case: EvalCase, config: KaizenConfig) -> tuple[str, bool, list[str]]:
    if config.mcp_server is None:
        raise ValueError(
            f"Eval case {case.id!r} uses task_prompt but no mcp_server is configured "
            f"in kaizen.yaml for project {config.project_name!r}"
        )

    result = await run_copilot_prompt_async(
        case.task_prompt,
        cwd=config.mcp_server.cwd or config.repo_path,
        session_id=str(uuid.uuid4()),  # each eval case gets its own isolated session
        model=config.model.copilot_runner_model,
        allow_all_tools=True,
        additional_mcp_config=build_mcp_config(config),
    )

    success = result.success
    if case.expect_output_contains:
        success = success and all(needle in result.text for needle in case.expect_output_contains)
    return result.text, success, result.tool_errors
