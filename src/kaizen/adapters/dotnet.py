"""Adapter for .NET/C# projects (the common case across .NET codebases)."""
from __future__ import annotations

import re

from kaizen.adapters.base import CommandResult, ProjectAdapter
from kaizen.trace.store import ErrorInfo

# MSBuild/dotnet build diagnostic, e.g.:
#   Program.cs(12,5): error CS0103: The name 'foo' does not exist [MyProj.csproj]
_MSBUILD_DIAG_RE = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s+"
    r"(?P<severity>error|warning)\s+(?P<code>\w+\d*):\s+(?P<message>.*)$",
    re.MULTILINE,
)

# `dotnet test` failure line, e.g.:
#   Failed MyNamespace.MyTests.MyTest_ShouldDoThing [12 ms]
_TEST_FAIL_RE = re.compile(r"^\s*Failed\s+(?P<test>\S+)\b.*$", re.MULTILINE)


class DotnetAdapter(ProjectAdapter):
    """Runs `dotnet build` / `dotnet test` and parses their output."""

    def parse_errors(self, result: CommandResult) -> list[ErrorInfo]:
        combined = f"{result.stdout}\n{result.stderr}"
        errors: list[ErrorInfo] = []

        for m in _MSBUILD_DIAG_RE.finditer(combined):
            if m.group("severity") != "error":
                continue
            errors.append(
                ErrorInfo(
                    file=m.group("file"),
                    line=int(m.group("line")),
                    column=int(m.group("column")),
                    code=m.group("code"),
                    message=m.group("message"),
                    raw=m.group(0),
                )
            )

        for m in _TEST_FAIL_RE.finditer(combined):
            errors.append(
                ErrorInfo(
                    code=m.group("test"),
                    message=f"Test failed: {m.group('test')}",
                    raw=m.group(0),
                )
            )

        if not errors and result.exit_code != 0:
            # Fall back: no structured match, but the command still failed.
            errors.append(
                ErrorInfo(message="Command failed with no parsable diagnostics.", raw=combined[-4000:])
            )

        return errors
