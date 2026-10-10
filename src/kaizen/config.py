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
    """Which language/build adapter to use for shelling out to the project.

    Built in: "dotnet" (parses `dotnet build`/`dotnet test` output) and
    "pytest" (parses pytest's short test summary). Each eval case's own
    `command` is what actually runs - this just selects which adapter
    parses that command's output into structured errors. Add a new
    language by implementing `ProjectAdapter` and registering it in
    `kaizen.adapters`.
    """

    name: str = "dotnet"  # "dotnet" | "pytest"
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


class AzureModelConfig(BaseModel):
    """Azure OpenAI connection details for the ``langgraph`` backend.

    ``auth_mode: "azure_ad"`` (the default) authenticates with the
    operator's own Azure identity via ``DefaultAzureCredential`` (picks up
    an existing ``az login`` session, a managed identity, etc.) - no API
    key is ever generated, stored, or distributed, which also sidesteps
    needing the (often separately-gated) ``listKeys`` permission. Use
    ``auth_mode: "api_key"`` only if AAD auth isn't an option; it reads
    ``AZURE_OPENAI_API_KEY`` from the environment.

    Overrides ``runner_model``/``fixer_model`` when a deployment is set for
    that role - this takes precedence over the plain "provider:model"
    string path.
    """

    endpoint: str
    api_version: str = "2024-10-21"
    auth_mode: str = "azure_ad"  # "azure_ad" | "api_key"
    runner_deployment: str | None = None
    fixer_deployment: str | None = None
    # Reasoning models (e.g. the gpt-6/gpt-5.6 family) reject function/tool
    # calls on the Chat Completions endpoint when a reasoning_effort is set
    # ("Function tools with reasoning_effort are not supported ... use
    # /v1/responses"). True routes through Azure's Responses API instead,
    # which lives on a separate, versionless "v1" surface
    # (`{endpoint}/openai/v1/`) with its own AAD token audience
    # (https://ai.azure.com/.default) - handled for you in azure_model.py.
    # Kaizen's Fixer/Runner always use tool calls, so this defaults on; set
    # False only for a deployment that doesn't support/need it (falls back
    # to the classic dated `api-version=...` Chat Completions surface).
    use_responses_api: bool = True


class ModelConfig(BaseModel):
    """Per-role model/backend selection.

    backend: "langgraph" (direct provider API calls - needs an API key per
        provider, or an ``azure`` block for Azure OpenAI; set via
        ``runner_model``/``fixer_model`` as a ``"provider:model"`` string)
        or "copilot_cli" (shells out to the already-authenticated GitHub
        Copilot CLI - no separate API key needed; set via
        ``copilot_runner_model``/``copilot_fixer_model`` using Copilot's
        own model catalog names, e.g. "claude-sonnet-4.5", or "auto").
        Pick per project depending on what's available; swap later with no
        code changes once a direct LLM deployment exists.
    """

    backend: str = "langgraph"  # "langgraph" | "copilot_cli"

    # Used when backend == "langgraph" and no `azure` deployment is set
    # for the role.
    runner_model: str = "anthropic:claude-haiku-4-5"
    fixer_model: str = "anthropic:claude-sonnet-4-5"

    # Used when backend == "langgraph" and pointed at Azure OpenAI.
    azure: AzureModelConfig | None = None

    # Used when backend == "copilot_cli". None lets Copilot auto-pick.
    copilot_runner_model: str | None = None
    copilot_fixer_model: str | None = None


class KaizenConfig(BaseModel):
    project_name: str
    repo_path: str
    eval_suite_path: str = "evals"
    mcp_server: McpServerConfig | None = None
    adapter: AdapterConfig = Field(default_factory=AdapterConfig)
    gate: GateConfig = Field(default_factory=GateConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    trace_store_path: str = ".kaizen/traces.jsonl"

    @classmethod
    def load(cls, path: str | Path) -> "KaizenConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)
