"""Structured failure trace store.

Raw logs are not enough for a Fixer agent to safely patch anything: it needs
to know *which version* of the prompt/tool-schema/code produced a failure.
``TraceRecord`` captures that; ``TraceStore`` is an append-only JSONL log
that both the Runner (writer) and Fixer (reader) share.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    """A single structured error extracted from tool/build/test output."""

    file: str | None = None
    line: int | None = None
    column: int | None = None
    code: str | None = None  # e.g. CS0103, or test name
    message: str = ""
    raw: str = ""


class TraceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    case_id: str
    project_name: str
    prompt_version: str | None = None
    tool_schema_version: str | None = None
    command: list[str] | None = None
    exit_code: int | None = None
    success: bool = False
    stdout: str = ""
    stderr: str = ""
    errors: list[ErrorInfo] = Field(default_factory=list)


class TraceStore:
    """Append-only JSONL trace log."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: TraceRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def read_all(self) -> list[TraceRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(TraceRecord.model_validate(json.loads(line)))
        return records

    def read_failures(self) -> list[TraceRecord]:
        return [r for r in self.read_all() if not r.success]
