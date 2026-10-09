"""Filesystem/shell tools exposed to the Fixer's LangGraph agent.

Tier-3 (locked) paths are hard-blocked here, in the tool itself - never
reachable, not even via human override. Tier-2 (application code) writes are
additionally gated through ``HumanInTheLoopMiddleware`` (see fixer_graph.py)
so a reviewer can approve/reject in real time, on top of the PR review that
always happens afterward.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from langchain_core.tools import tool

from kaizen.config import PatchTier
from kaizen.fixer.tiering import classify_tier


def make_fixer_tools(repo_path: str, touched_files: list[str]):
    """Builds the tool set for one Fixer session, bound to `repo_path`.

    `touched_files` is mutated in place so the caller can inspect which
    files were written/edited after the agent run finishes.
    """
    root = Path(repo_path).resolve()

    def _resolve(rel_path: str) -> Path:
        p = (root / rel_path).resolve()
        if root not in p.parents and p != root:
            raise ValueError(f"Path {rel_path!r} escapes the repository root.")
        return p

    @tool
    def read_file(path: str) -> str:
        """Read a text file's contents, given a path relative to the repo root."""
        return _resolve(path).read_text(encoding="utf-8")

    @tool
    def write_file(path: str, content: str) -> str:
        """Overwrite (or create) a text file, given a path relative to the repo root."""
        if classify_tier(path) == PatchTier.TIER_3_LOCKED:
            return f"DENIED: {path!r} is a locked (Tier 3) path; Fixer may never write to it."
        target = _resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        touched_files.append(path)
        return f"Wrote {path}"

    @tool
    def edit_file(path: str, old_str: str, new_str: str) -> str:
        """Replace the first occurrence of `old_str` with `new_str` in a file."""
        if classify_tier(path) == PatchTier.TIER_3_LOCKED:
            return f"DENIED: {path!r} is a locked (Tier 3) path; Fixer may never edit it."
        target = _resolve(path)
        text = target.read_text(encoding="utf-8")
        if old_str not in text:
            return f"ERROR: old_str not found in {path}"
        target.write_text(text.replace(old_str, new_str, 1), encoding="utf-8")
        touched_files.append(path)
        return f"Edited {path}"

    @tool
    def run_bash(command: str) -> str:
        """Run a read-only/diagnostic shell command (e.g. `grep`, `dotnet build`) in the repo."""
        result = subprocess.run(
            command, shell=True, cwd=root, capture_output=True, text=True, timeout=120
        )
        return f"exit={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    return [read_file, write_file, edit_file, run_bash]
