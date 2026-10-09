"""Configuration model for a Kaizen run.

A single YAML file (``kaizen.yaml``) at the root of a *target* project
describes everything Kaizen needs to run its loop against that project.
This keeps Kaizen itself project-agnostic: adding a new target project
means authoring a config + eval suite, not changing Kaizen's code.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PatchTier(str, Enum):
    """Scopes what a Fixer agent is allowed to touch autonomously.

    TIER_1_SAFE: prompts, MCP tool descriptions, config/docs. Low risk,
        reversible, text-only. Can go through a lightweight review.
    TIER_2_CODE: application source code. Always requires full human review.
    TIER_3_LOCKED: secrets, infra, deploy configs. Fixer must never touch.
    """

    TIER_1_SAFE = "tier_1_safe"
    TIER_2_CODE = "tier_2_code"
    TIER_3_LOCKED = "tier_3_locked"


class McpServerConfig(BaseModel):
    """How to launch/connect to the target project's MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


class AdapterConfig(BaseModel):
    """Which language/build adapter to use for shelling out to the project."""

    name: str = "dotnet"  # e.g. "dotnet", "generic"
    build_command: list[str] = Field(default_factory=lambda: ["dotnet", "build"])
    test_command: list[str] = Field(default_factory=lambda: ["dotnet", "test"])


class GateConfig(BaseModel):
    """Human-in-the-loop PR gate settings."""

    require_review_for: list[PatchTier] = Field(
        default_factory=lambda: [PatchTier.TIER_2_CODE]
    )
    auto_apply_tiers: list[PatchTier] = Field(default_factory=list)
    base_branch: str = "main"
    branch_prefix: str = "kaizen/fix"


class KaizenConfig(BaseModel):
    project_name: str
    repo_path: str
    eval_suite_path: str = "evals"
    mcp_server: McpServerConfig | None = None
    adapter: AdapterConfig = Field(default_factory=AdapterConfig)
    gate: GateConfig = Field(default_factory=GateConfig)
    trace_store_path: str = ".kaizen/traces.jsonl"

    @classmethod
    def load(cls, path: str | Path) -> "KaizenConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)
