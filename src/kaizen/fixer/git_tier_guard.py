"""Post-hoc Tier-3 enforcement for backends that can't hook individual tool
calls the way LangGraph's ``HumanInTheLoopMiddleware`` does (e.g. the
Copilot CLI backend). Diffs the working tree after a session and hard-
reverts any Tier-3 (locked) file regardless of what the agent did.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from kaizen.config import PatchTier
from kaizen.fixer.tiering import classify_tier


def changed_files(repo_path: str, base_ref: str) -> list[str]:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", base_ref],
        cwd=repo_path, capture_output=True, text=True, check=True,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo_path, capture_output=True, text=True, check=True,
    )
    files = set(tracked.stdout.splitlines()) | set(untracked.stdout.splitlines())
    return sorted(f for f in files if f)


def revert_locked_paths(repo_path: str, base_ref: str) -> list[str]:
    """Hard-reverts any Tier-3 file touched since `base_ref` - restoring it
    from base if it existed there, deleting it otherwise. Returns the
    surviving (non-reverted) touched files.
    """
    touched = changed_files(repo_path, base_ref)
    surviving: list[str] = []
    for f in touched:
        if classify_tier(f) != PatchTier.TIER_3_LOCKED:
            surviving.append(f)
            continue
        existed_at_base = subprocess.run(
            ["git", "cat-file", "-e", f"{base_ref}:{f}"], cwd=repo_path, capture_output=True
        ).returncode == 0
        if existed_at_base:
            subprocess.run(["git", "checkout", base_ref, "--", f], cwd=repo_path, check=True)
        else:
            # Untracked at base: `git rm` only works on tracked files, so
            # delete it directly (and `git rm` it too, in case it's staged).
            target = Path(repo_path) / f
            target.unlink(missing_ok=True)
            subprocess.run(["git", "rm", "-f", "--ignore-unmatch", "--cached", f], cwd=repo_path, capture_output=True)
    return surviving
