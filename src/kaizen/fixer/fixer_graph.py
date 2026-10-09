"""Builds and runs the Fixer's LangGraph agent session.

Provider-agnostic: `config.model.fixer_model` is a ``"provider:model"``
string (LangChain's `init_chat_model` convention), so swapping Anthropic for
OpenAI/Bedrock/a local model is a one-line config change, not a code change.

Tier-2 (application code) writes/edits pause for human approval via
`HumanInTheLoopMiddleware` - on top of the hard Tier-3 block in tools.py and
the PR review that always happens afterward. This graph is also exported
(see graphs.py) so LangGraph Studio can visualize/approve these interrupts
live, in addition to the CLI prompt below.
"""
from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from kaizen.config import KaizenConfig, PatchTier
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
    model: str,
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


async def run_fix_session(prompt: str, config: KaizenConfig) -> list[str]:
    """Runs the Fixer agent on `prompt`; resolves any Tier-2 approval
    interrupts via a console y/n prompt. Returns the list of touched files.
    """
    touched_files: list[str] = []
    agent = build_fixer_agent(
        config.model.fixer_model, config.repo_path, touched_files, checkpointer=InMemorySaver()
    )
    thread_config = {"configurable": {"thread_id": f"fixer-{id(touched_files)}"}}

    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config=thread_config)

    while "__interrupt__" in result:
        interrupt = result["__interrupt__"][0]
        request = interrupt.value["action_requests"][0]
        print(f"\n[Fixer] Approval required: {request.get('description', request)}")
        answer = input("Approve this Tier-2 code change? [y/N]: ").strip().lower()
        decision = "approve" if answer == "y" else "reject"
        result = await agent.ainvoke(Command(resume=[{"type": decision}]), config=thread_config)

    return touched_files
