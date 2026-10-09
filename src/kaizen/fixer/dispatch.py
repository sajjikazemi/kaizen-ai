"""Dispatches a Fixer session to the configured backend.

``config.model.backend`` picks "langgraph" (direct provider API, needs an
API key) or "copilot_cli" (shells out to the already-authenticated GitHub
Copilot CLI, no API key needed). Everything above this layer (FixerAgent,
tiering, PR gate) is backend-agnostic.
"""
from __future__ import annotations

import uuid

from kaizen.config import KaizenConfig
from kaizen.trace.store import TraceRecord


def session_id_for(record: TraceRecord) -> str:
    """Deterministic per-case session id, stable across retries/follow-ups
    for the same failing case, isolated from other cases."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"kaizen-fixer-{record.project_name}-{record.case_id}"))


async def run_fix_session(prompt: str, config: KaizenConfig, session_id: str | None = None) -> list[str]:
    if config.model.backend == "copilot_cli":
        from kaizen.fixer.backends.copilot_cli_backend import run_fix_session as _run
    else:
        from kaizen.fixer.backends.langgraph_backend import run_fix_session as _run
    return await _run(prompt, config, session_id=session_id)


def open_chat_session(config: KaizenConfig, session_id: str | None = None):
    """Opens a multi-turn Fixer session for `kaizen chat` - same backends as
    `run_fix_session`, but reusable across multiple `.send()` calls so
    follow-up messages continue the same conversation instead of starting a
    fresh one-shot session each time."""
    if config.model.backend == "copilot_cli":
        from kaizen.fixer.backends.copilot_cli_backend import CopilotCliFixerSession as _Session
    else:
        from kaizen.fixer.backends.langgraph_backend import LangGraphFixerSession as _Session
    return _Session(config, session_id)
