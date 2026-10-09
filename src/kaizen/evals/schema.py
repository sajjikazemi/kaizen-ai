"""Eval suite schema.

An *eval suite* is the signal that makes self-fixing safe: every project that
wants Kaizen to run against it defines one. Each case is either a shell
command (e.g. ``dotnet test``) or a natural-language task to hand to the
Runner agent over MCP, plus a pass/fail criterion.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    id: str
    description: str = ""
    # One of these two must be set.
    command: list[str] | None = None
    task_prompt: str | None = None
    expect_exit_code: int = 0
    expect_output_contains: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300


class EvalSuite(BaseModel):
    name: str
    cases: list[EvalCase]

    @classmethod
    def load(cls, path: str | Path) -> "EvalSuite":
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
