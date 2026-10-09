"""Classifies a file path into a patch risk tier.

Used by the Fixer agent to decide what it may touch autonomously versus
what always needs a human in the loop, independent of language/project.
"""
from __future__ import annotations

import fnmatch

from kaizen.config import PatchTier

# Matched against any path *component* (directory name or filename).
_TIER_3_DIR_NAMES = {"secrets", "infra", "terraform", "workflows"}
_TIER_3_FILE_PATTERNS = ["*.pfx", "*.pem", "*.key", ".env*", "*secret*.json", "*.tfstate"]

_TIER_1_DIR_NAMES = {"prompts", "evals", "tool_descriptions"}
_TIER_1_FILE_PATTERNS = ["*.prompt.md", "*.eval.yaml", "*.md", "kaizen.yaml"]


def classify_tier(path: str) -> PatchTier:
    normalized = path.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    filename = parts[-1] if parts else normalized
    dir_names = set(parts[:-1])

    if dir_names & _TIER_3_DIR_NAMES or any(
        fnmatch.fnmatch(filename, pat) for pat in _TIER_3_FILE_PATTERNS
    ):
        return PatchTier.TIER_3_LOCKED

    if dir_names & _TIER_1_DIR_NAMES or any(
        fnmatch.fnmatch(filename, pat) for pat in _TIER_1_FILE_PATTERNS
    ):
        return PatchTier.TIER_1_SAFE

    return PatchTier.TIER_2_CODE
