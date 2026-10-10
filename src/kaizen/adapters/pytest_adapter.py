"""Adapter for Python projects that use pytest."""
from __future__ import annotations

import re

from kaizen.adapters.base import CommandResult, ProjectAdapter
from kaizen.trace.store import ErrorInfo

# pytest's short test summary line, e.g.:
#   FAILED test_calculator.py::test_add - assert -1 == 5
#   ERROR test_calculator.py::test_setup - ModuleNotFoundError: no module named 'foo'
_SUMMARY_RE = re.compile(
    r"^(?P<status>FAILED|ERROR)\s+(?P<node>\S+?)(?:\s+-\s+(?P<reason>.*))?$",
    re.MULTILINE,
)


class PytestAdapter(ProjectAdapter):
    """Runs `pytest` and parses its short test summary output."""

    def parse_errors(self, result: CommandResult) -> list[ErrorInfo]:
        combined = f"{result.stdout}\n{result.stderr}"
        errors: list[ErrorInfo] = []

        for m in _SUMMARY_RE.finditer(combined):
            node = m.group("node")
            file = node.split("::", 1)[0]
            reason = m.group("reason") or f"{m.group('status').title()}: {node}"
            errors.append(
                ErrorInfo(
                    file=file,
                    code=node,
                    message=reason,
                    raw=m.group(0),
                )
            )

        if not errors and result.exit_code != 0:
            # Fall back: no structured match, but the command still failed.
            errors.append(
                ErrorInfo(message="Command failed with no parsable diagnostics.", raw=combined[-4000:])
            )

        return errors
