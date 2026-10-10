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
from kaizen.prompts import FIXER_SYSTEM_PROMPT


def _requires_code_review(req: Any) -> bool:  # req: ToolCallRequest
    path = req.tool_call.get("args", {}).get("path", "")
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
        **kwargs,  # type: ignore[call-overload]  # conditionally omitting `checkpointer`
        # (vs. passing it as None) is intentional - see the docstring above - but defeats
        # create_agent's static overload resolution.
    )


def _shorten(value: Any, length: int = 160) -> str:
    text = str(value)
    return text if len(text) <= length else text[: length - 3] + "..."


_TOOL_DESCRIPTIONS = {
    "read_file": lambda args: f"Reading {args.get('path', '?')}",
    "write_file": lambda args: f"Writing {args.get('path', '?')}",
    "edit_file": lambda args: f"Editing {args.get('path', '?')}",
    "run_bash": lambda args: f"Running: {_shorten(args.get('command', '?'), 100)}",
}


def _describe_tool_call(name: str | None, args: dict) -> str:
    describe = _TOOL_DESCRIPTIONS.get(name or "")
    return describe(args) if describe else f"Calling {name}"


def _describe_tool_result(content: str) -> str:
    """Tool results (file contents, command output) are often long and not
    meant for a human to read live - show a short, natural status instead
    of dumping the raw payload."""
    if content.startswith("exit="):
        first_line = content.splitlines()[0]
        code = first_line.split("=", 1)[1] if "=" in first_line else "?"
        return "done" if code == "0" else f"failed (exit {code})"
    if content.startswith(("DENIED", "ERROR")):
        return _shorten(content, 150)
    return "done"


def _print_progress(message: Any) -> None:
    """Prints one short, natural-language line per new tool-call/result, so
    the terminal shows live progress instead of going silent until the
    session finishes (or crashes) - or dumping raw dicts/file contents."""
    role = getattr(message, "type", "message")
    if role == "human":
        return  # that's just the message we sent - no need to echo it back

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        for call in tool_calls:
            print(f"  [Fixer] {_describe_tool_call(call.get('name'), call.get('args', {}))}")
        return

    content = getattr(message, "content", None)
    if role == "tool":
        if isinstance(content, str) and content.strip():
            print(f"  [Fixer]   -> {_describe_tool_result(content)}")
        return

    if isinstance(content, str) and content.strip():
        print(f"  [Fixer] {_shorten(content, 200)}")


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
    """Single-turn convenience wrapper around `LangGraphFixerSession`, used
    by `kaizen fix`. Raises `FixerSessionError` (short, human-readable
    message) instead of letting a raw provider/library traceback bubble up
    to the CLI.
    """
    session = LangGraphFixerSession(config, session_id)
    return await session.send(prompt)


class LangGraphFixerSession:
    """A multi-turn Fixer conversation. Builds the agent + its in-memory
    checkpointer once and reuses them across calls to `send()`, so a
    follow-up message (e.g. from `kaizen chat`) continues the same
    conversation - unlike `run_fix_session`, which is single-turn by
    design (a fresh session every `kaizen fix` invocation).
    """

    def __init__(self, config: KaizenConfig, session_id: str | None = None):
        self.touched_files: list[str] = []
        self.agent = build_fixer_agent(
            resolve_model(config.model, "fixer"), config.repo_path, self.touched_files, checkpointer=InMemorySaver()
        )
        self.thread_config = {"configurable": {"thread_id": session_id or f"fixer-{id(self)}"}}

    async def send(self, message: str) -> list[str]:
        """Sends one message in this session; resolves any Tier-2 approval
        interrupts via a console y/n prompt. Returns the files touched
        across the whole session so far (not just this turn)."""
        try:
            result = await _stream_to_completion(
                self.agent, {"messages": [{"role": "user", "content": message}]}, self.thread_config
            )

            while "__interrupt__" in result:
                interrupt = result["__interrupt__"][0]
                requests = interrupt.value["action_requests"]
                decisions = []
                for request in requests:
                    print(f"\n[Fixer] Approval required: {request.get('description', request)}")
                    answer = input("Approve this Tier-2 code change? [y/N]: ").strip().lower()
                    decisions.append({"type": "approve" if answer == "y" else "reject"})
                result = await _stream_to_completion(
                    self.agent, Command(resume={"decisions": decisions}), self.thread_config
                )
        except Exception as exc:
            raise FixerSessionError(summarize_exception(exc)) from exc

        return self.touched_files
