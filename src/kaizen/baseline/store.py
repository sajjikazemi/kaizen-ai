"""Versioned full-suite baseline snapshots.

A snapshot is a per-case pass/fail map from a full eval-suite run, keyed by
the git SHA it was taken at. It's the "ground truth" both the treatment and
control splits are compared against - refreshed on a cadence (e.g. nightly,
or pre-merge-to-main), never recomputed on every candidate fix.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field


class BaselineSnapshot(BaseModel):
    git_sha: str
    project_name: str
    created_at: float = Field(default_factory=time.time)
    results: dict[str, bool]  # case_id -> passed


class BaselineStore:
    """A small JSON file mapping git_sha -> BaselineSnapshot."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, snapshot: BaselineSnapshot) -> None:
        data = self._read()
        data[snapshot.git_sha] = json.loads(snapshot.model_dump_json())
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, git_sha: str) -> BaselineSnapshot | None:
        entry = self._read().get(git_sha)
        return BaselineSnapshot.model_validate(entry) if entry else None

    def latest(self) -> BaselineSnapshot | None:
        data = self._read()
        if not data:
            return None
        newest = max(data.values(), key=lambda s: s["created_at"])
        return BaselineSnapshot.model_validate(newest)
