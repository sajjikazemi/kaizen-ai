"""Adapter interface: how Kaizen executes work against a target project.

The agent layer never needs to understand a target language's syntax. It
shells out to the project's own build/test tooling and reads the output.
Adapters only need to know how to *run* that tooling and how to turn its
output into structured ``ErrorInfo`` objects.
"""
from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass

from kaizen.trace.store import ErrorInfo


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


class ProjectAdapter(ABC):
    """Base class for language/project-specific adapters."""

    def __init__(self, repo_path: str, timeout_seconds: int = 300):
        self.repo_path = repo_path
        self.timeout_seconds = timeout_seconds

    def run(self, command: list[str]) -> CommandResult:
        proc = subprocess.run(
            command,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        return CommandResult(
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    @abstractmethod
    def parse_errors(self, result: CommandResult) -> list[ErrorInfo]:
        """Turn a command's raw output into structured errors."""
        raise NotImplementedError
