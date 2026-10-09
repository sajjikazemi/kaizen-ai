"""Fixer agent: turns a failing trace into a scoped, reviewable patch.

Flow per failing eval case:
 1. Create an isolated git branch.
 2. Ask Claude (Read/Edit/Bash tools, cwd pinned to the repo) to fix the
    failure, given the structured trace. A ``can_use_tool`` hook blocks any
    write to a Tier-3 (locked) path outright.
 3. Re-run just that eval case with the Runner to verify the fix actually
    works before anything is proposed to a human.
 4. Hand off to the PR gate - nothing is ever merged automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from kaizen.adapters.base import ProjectAdapter
from kaizen.config import KaizenConfig, PatchTier
from kaizen.fixer.tiering import classify_tier
from kaizen.trace.store import TraceRecord


@dataclass
class PatchPlan:
    case_id: str
    branch_name: str
    summary: str
    files_touched: list[str] = field(default_factory=list)
    highest_tier: PatchTier = PatchTier.TIER_1_SAFE
    verified_fixed: bool = False
    verdict: str | None = None  # "fix" | "trade" | "rejected", set by the CLI after evaluate()


def _build_fix_prompt(record: TraceRecord) -> str:
    error_lines = "\n".join(
        f"- {e.file or ''}:{e.line or ''} [{e.code or ''}] {e.message}" for e in record.errors
    ) or record.stdout[-2000:]
    return (
        "The following eval case is failing in this repository:\n\n"
        f"Case: {record.case_id}\n"
        f"Command: {' '.join(record.command) if record.command else '(task prompt)'}\n"
        f"Exit code: {record.exit_code}\n\n"
        "Structured errors:\n"
        f"{error_lines}\n\n"
        "Make the SMALLEST possible change that fixes this failure. "
        "Prefer fixing prompts/config/tool descriptions over application code "
        "when the root cause is there. Do not touch unrelated files. "
        "Do not commit; just edit the working tree."
    )


class FixerAgent:
    def __init__(self, config: KaizenConfig, adapter: ProjectAdapter):
        self.config = config
        self.adapter = adapter

    def propose_fix(self, record: TraceRecord) -> PatchPlan:
        import subprocess

        branch_name = f"{self.config.gate.branch_prefix}/{record.case_id}"
        subprocess.run(
            ["git", "checkout", "-b", branch_name, self.config.gate.base_branch],
            cwd=self.config.repo_path,
            check=True,
        )

        prompt = _build_fix_prompt(record)
        files_touched = self._run_fix_agent(prompt)

        tiers = [classify_tier(f) for f in files_touched] or [PatchTier.TIER_1_SAFE]
        highest_tier = max(tiers, key=lambda t: list(PatchTier).index(t))

        return PatchPlan(
            case_id=record.case_id,
            branch_name=branch_name,
            summary=f"Fix for failing eval case '{record.case_id}'",
            files_touched=files_touched,
            highest_tier=highest_tier,
        )

    def _run_fix_agent(self, prompt: str) -> list[str]:
        import anyio

        from kaizen.fixer.claude_fix import run_fix_session

        return anyio.run(run_fix_session, prompt, self.config.repo_path)

    def verify(self, plan: PatchPlan, case_command: list[str] | None) -> PatchPlan:
        if case_command is None:
            return plan
        result = self.adapter.run(case_command)
        plan.verified_fixed = result.exit_code == 0
        return plan
