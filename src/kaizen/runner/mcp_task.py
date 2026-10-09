"""Dispatches a task_prompt eval case to the configured backend.

``config.model.backend`` picks "langgraph" (direct provider API, needs an
API key) or "copilot_cli" (shells out to the already-authenticated GitHub
Copilot CLI, no API key needed). Everything above this layer (RunnerAgent,
trace store, evaluate) is backend-agnostic.
"""
from __future__ import annotations

from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalCase


async def run_mcp_task(case: EvalCase, config: KaizenConfig) -> tuple[str, bool, list[str]]:
    if config.model.backend == "copilot_cli":
        from kaizen.runner.backends.copilot_cli_backend import run_mcp_task as _run
    else:
        from kaizen.runner.backends.langgraph_backend import run_mcp_task as _run
    return await _run(case, config)
