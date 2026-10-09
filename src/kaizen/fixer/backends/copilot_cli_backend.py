"""Fixer backend that runs the fix session through the already-authenticated
GitHub Copilot CLI instead of a direct LLM provider API - no separate API
key needed.

Tier-3 enforcement can't be hooked per-tool-call the way LangGraph's
``HumanInTheLoopMiddleware`` does (the CLI has no such extension point), so
it's applied post-hoc: after the session finishes, any Tier-3 (locked) file
in the diff is hard-reverted before anything is returned to the caller.
Tier-2 review still happens the same way either backend is used - via the
PR gate, which always requires human approval for Tier-2/3 changes.
"""
from __future__ import annotations

from kaizen.config import KaizenConfig
from kaizen.copilot_cli.run import CopilotCliNotFound, run_copilot_prompt_async
from kaizen.fixer.errors import FixerSessionError
from kaizen.fixer.git_tier_guard import revert_locked_paths
from kaizen.prompts import FIXER_SYSTEM_PROMPT, with_system_prompt


async def run_fix_session(prompt: str, config: KaizenConfig, session_id: str | None = None) -> list[str]:
    session = CopilotCliFixerSession(config, session_id)
    return await session.send(prompt)


class CopilotCliFixerSession:
    """A multi-turn Fixer conversation via the Copilot CLI. Continuity
    across turns - even across separate process invocations - is handled by
    Copilot CLI's own on-disk session persistence, keyed by `session_id`;
    this class just keeps track of which turn is first (to prepend the
    system prompt once) and the session id itself."""

    def __init__(self, config: KaizenConfig, session_id: str | None = None):
        import uuid

        self.config = config
        self.session_id = session_id or str(uuid.uuid4())
        self._first_turn = True

    async def send(self, message: str) -> list[str]:
        prompt = with_system_prompt(FIXER_SYSTEM_PROMPT, message) if self._first_turn else message
        self._first_turn = False

        print(f"  [Fixer:copilot_cli] session {self.session_id}...")
        try:
            result = await run_copilot_prompt_async(
                prompt,
                cwd=self.config.repo_path,
                session_id=self.session_id,
                model=self.config.model.copilot_fixer_model,
                allow_all_tools=True,
            )
        except CopilotCliNotFound as exc:
            raise FixerSessionError(str(exc)) from exc

        if not result.success:
            detail = "; ".join(result.tool_errors) if result.tool_errors else (result.text[:300] or "(no output)")
            print(f"  [Fixer:copilot_cli] session reported issues: {detail}")
        else:
            print(f"  [Fixer:copilot_cli] session finished (exit_code={result.exit_code})")

        return revert_locked_paths(self.config.repo_path, self.config.gate.base_branch)
