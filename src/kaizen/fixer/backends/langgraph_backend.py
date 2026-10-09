"""Builds and runs the Fixer's LangGraph agent session.

Provider-agnostic: `config.model.fixer_model` is a ``"provider:model"``
string (LangChain's `init_chat_model` convention), or `config.model.azure`
names an Azure OpenAI deployment - swapping providers is a config change,
not a code change (see `kaizen.azure_model.resolve_model`).

Tier-2 (application code) writes/edits pause for human approval via
`HumanInTheLoopMiddleware` - on top of the hard Tier-3 block in tools.py and
the PR review that always happens afterward. This graph is also exported
(see graphs.py) so LangGraph Studio can visualize/approve these interrupts
live, in addition to the CLI prompt below.
"""
from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from kaizen.azure_model import resolve_model
from kaizen.config import KaizenConfig, PatchTier
from kaizen.fixer.errors import FixerSessionError, summarize_exception
from kaizen.fixer.tiering import classify_tier
from kaizen.fixer.tools import make_fixer_tools

FIXER_SYSTEM_PROMPT = (
    "You are a precise, conservative software-fixing agent. Make the SMALLEST "
    "possible change that fixes the described failure. Prefer fixing "
    "prompts/config/tool descriptions over application code when the root "
    "cause is there. Do not touch unrelated files. Never attempt to write "
    "secrets, infra, or CI/CD config files."
)


def _requires_code_review(tool_call, state, runtime) -> bool:  # noqa: ANN001
    path = tool_call.get("args", {}).get("path", "")
    return classify_tier(path) == PatchTier.TIER_2_CODE


def build_fixer_agent(
    model: str | Any,
    repo_path: str,
    touched_files: list[str],
    checkpointer: object | None = None,
):
    """`checkpointer` should be omitted when served via `langgraph dev`/Studio
    or any LangGraph Platform deployment - the platform injects its own
    persistence and rejects a custom one. Pass an explicit checkpointer (e.g.
    `InMemorySaver()`) only for the standalone CLI path, which has no
    platform layer to provide one.
    """
    tools = make_fixer_tools(repo_path, touched_files)
    middleware = [
        HumanInTheLoopMiddleware(
            interrupt_on={
                "write_file": {"allowed_decisions": ["approve", "reject"], "when": _requires_code_review},
                "edit_file": {"allowed_decisions": ["approve", "reject"], "when": _requires_code_review},
            },
            description_prefix="Fixer wants to modify application code (Tier 2) - review required",
        )
    ]
    kwargs = {"checkpointer": checkpointer} if checkpointer is not None else {}
    return create_agent(
        model,
        tools,
        system_prompt=FIXER_SYSTEM_PROMPT,
        middleware=middleware,
        **kwargs,
    )


def _shorten(value: Any, length: int = 160) -> str:
    text = str(value)
    return text if len(text) <= length else text[: length - 3] + "..."


def _print_progress(message: Any) -> None:
    """Prints one short, human-readable line per new message/tool-call, so
    the terminal shows live progress instead of going silent until the
    session finishes (or crashes)."""
    role = getattr(message, "type", "message")
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        for call in tool_calls:
            print(f"  [Fixer] -> {call.get('name')}({_shorten(call.get('args', {}), 100)})")
        return
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        print(f"  [Fixer] <- {role}: {_shorten(content)}")


async def _stream_to_completion(agent, agent_input: Any, thread_config: dict) -> dict:
    """Streams the run, printing progress as it happens, and returns the
    final cumulative state (same shape `ainvoke` would return)."""
    result: dict = {}
    seen = 0
    async for chunk in agent.astream(agent_input, config=thread_config, stream_mode="values"):
        result = chunk
        messages = result.get("messages", [])
        for message in messages[seen:]:
            _print_progress(message)
        seen = len(messages)
    return result


async def run_fix_session(prompt: str, config: KaizenConfig, session_id: str | None = None) -> list[str]:
    """Runs the Fixer agent on `prompt`; resolves any Tier-2 approval
    interrupts via a console y/n prompt. Returns the list of touched files.

    `session_id`, if given, is reused as the LangGraph thread id (so a
    retry/follow-up continues the same conversation) - otherwise a fresh one
    is generated, matching the Copilot CLI backend's session semantics.

    Raises `FixerSessionError` (short, human-readable message) instead of
    letting a raw provider/library traceback bubble up to the CLI.
    """
    touched_files: list[str] = []
    agent = build_fixer_agent(
        resolve_model(config.model, "fixer"), config.repo_path, touched_files, checkpointer=InMemorySaver()
    )
    thread_config = {"configurable": {"thread_id": session_id or f"fixer-{id(touched_files)}"}}

    try:
        result = await _stream_to_completion(
            agent, {"messages": [{"role": "user", "content": prompt}]}, thread_config
        )

        while "__interrupt__" in result:
            interrupt = result["__interrupt__"][0]
            request = interrupt.value["action_requests"][0]
            print(f"\n[Fixer] Approval required: {request.get('description', request)}")
            answer = input("Approve this Tier-2 code change? [y/N]: ").strip().lower()
            decision = "approve" if answer == "y" else "reject"
            result = await _stream_to_completion(agent, Command(resume=[{"type": decision}]), thread_config)
    except Exception as exc:
        raise FixerSessionError(summarize_exception(exc)) from exc

    return touched_files
