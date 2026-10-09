"""Thin subprocess wrapper around the GitHub Copilot CLI's non-interactive
(``-p``/``--prompt``) mode.

Lets Kaizen drive an agent "session" without needing a separate LLM
provider API key: each invocation uses the operator's already-authenticated
Copilot CLI subscription. Pass the same `session_id` across calls to
continue a conversation (e.g. a human follow-up after a rejected edit); a
fresh UUID per task gives full isolation between unrelated tasks.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field


class CopilotCliNotFound(RuntimeError):
    pass


@dataclass
class CopilotResult:
    text: str
    success: bool
    exit_code: int
    session_id: str | None
    tool_errors: list[str] = field(default_factory=list)
    raw_events: list[dict] = field(default_factory=list)


def _parse_jsonl(stdout: str) -> tuple[str, int | None, str | None, list[str], list[dict]]:
    """Parses Copilot CLI's ``--output-format json`` (JSONL) stream."""
    text_by_message: dict[str, str] = {}
    tool_errors: list[str] = []
    exit_code: int | None = None
    session_id: str | None = None
    events: list[dict] = []

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        etype = event.get("type", "")
        data = event.get("data", {}) or {}

        if etype == "assistant.message":
            text_by_message[data.get("messageId", "")] = data.get("content", "")
        elif etype == "session.mcp_server_status_changed" and data.get("status") == "failed":
            tool_errors.append(f"MCP server {data.get('serverName')!r} failed: {data.get('error')}")
        elif etype == "result":
            exit_code = event.get("exitCode")
            session_id = event.get("sessionId")

    full_text = "\n".join(t for t in text_by_message.values() if t)
    return full_text, exit_code, session_id, tool_errors, events


def run_copilot_prompt(
    prompt: str,
    *,
    cwd: str,
    session_id: str | None = None,
    model: str | None = None,
    allow_all_tools: bool = True,
    allow_tools: list[str] | None = None,
    deny_tools: list[str] | None = None,
    additional_mcp_config: dict | None = None,
    add_dirs: list[str] | None = None,
    timeout_seconds: int = 600,
) -> CopilotResult:
    """Runs one non-interactive Copilot CLI session and returns its result.

    Blocking/synchronous - call via `run_copilot_prompt_async` from async
    code.
    """
    cmd = ["copilot", "-p", prompt, "--output-format", "json", "--log-level", "none"]

    if session_id:
        cmd += ["--session-id", session_id]
    if model:
        cmd += ["--model", model]
    if allow_all_tools:
        cmd += ["--allow-all-tools"]
    for t in allow_tools or []:
        cmd += ["--allow-tool", t]
    for t in deny_tools or []:
        cmd += ["--deny-tool", t]
    for d in add_dirs or []:
        cmd += ["--add-dir", d]
    if additional_mcp_config:
        cmd += ["--additional-mcp-config", json.dumps(additional_mcp_config)]

    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_seconds
        )
    except FileNotFoundError as exc:
        raise CopilotCliNotFound(
            "The 'copilot' CLI was not found on PATH. Install GitHub Copilot CLI "
            "and run `copilot /login` first."
        ) from exc

    text, exit_code, parsed_session_id, tool_errors, events = _parse_jsonl(proc.stdout)
    if exit_code is None:
        exit_code = proc.returncode

    return CopilotResult(
        text=text,
        success=(exit_code == 0) and not tool_errors,
        exit_code=exit_code,
        session_id=parsed_session_id or session_id,
        tool_errors=tool_errors,
        raw_events=events,
    )


async def run_copilot_prompt_async(*args, **kwargs) -> CopilotResult:
    import anyio

    return await anyio.to_thread.run_sync(lambda: run_copilot_prompt(*args, **kwargs))
