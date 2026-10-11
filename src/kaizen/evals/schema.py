"""Eval suite schema.

An *eval suite* is the signal that makes self-fixing safe: every project that
wants Kaizen to run against it defines one. Each case is exactly one of:
a shell command (e.g. ``dotnet test``), a scripted MCP tool call (one
``tool``/``arguments`` pair, checked deterministically - no LLM involved),
or a natural-language task handed to the Runner agent over MCP. Plus a
pass/fail criterion either way.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class McpToolCallSpec(BaseModel):
    """One scripted MCP tool call: no LLM, no agent reasoning - just invoke
    `tool` with `arguments` over the target's MCP server and check the raw
    result. Cheap and deterministic, unlike a `task_prompt` case - meant for
    isolating a single tool's behavior (e.g. while diagnosing whether a
    failure traces to the tool's schema/implementation vs. the agent's
    prompt, which a full agent run can't cleanly distinguish)."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class EvalCase(BaseModel):
    id: str
    description: str = ""
    # Exactly one of these three must be set.
    command: list[str] | None = None
    mcp_tool_call: McpToolCallSpec | None = None
    task_prompt: str | None = None
    expect_exit_code: int = 0
    expect_output_contains: list[str] = Field(default_factory=list)
    # mcp_tool_call only: should the call itself report an error
    # (CallToolResult.isError)? Most cases want this False (expect success).
    expect_is_error: bool = False
    timeout_seconds: int = 300
    # Feature/category labels, e.g. ["device-provisioning", "auth"]. Used to
    # build the treatment split (cases sharing a tag with a failing case)
    # and to stratify the control split.
    tags: list[str] = Field(default_factory=list)


class EvalSuite(BaseModel):
    name: str
    cases: list[EvalCase]

    @classmethod
    def load(cls, path: str | Path) -> EvalSuite:
        p = Path(path)
        if p.is_dir():
            cases: list[EvalCase] = []
            suite_name = p.name
            for f in sorted(p.glob("*.eval.yaml")):
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                cases.append(EvalCase.model_validate(data))
            return cls(name=suite_name, cases=cases)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return cls.model_validate(data)
