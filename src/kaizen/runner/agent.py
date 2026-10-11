"""Runner agent: executes a project's eval suite and records failures.

Three kinds of eval cases are supported:

* ``command`` cases - deterministic shell commands (``dotnet build``,
  ``dotnet test``). These don't need an LLM at all; the adapter runs them
  and parses structured errors directly. Cheap and fast - prefer these.
* ``mcp_tool_call`` cases - one scripted MCP tool call (no LLM/agent),
  checked against the raw ``CallToolResult``. Cheap and deterministic
  like ``command`` cases, but exercises the target's MCP server directly -
  useful for isolating a single tool's behavior from everything an
  agent's reasoning might otherwise mask.
* ``task_prompt`` cases - natural-language tasks handed to Claude over the
  target project's MCP server (e.g. "add a customer record via the
  provisioning API and confirm it appears"). Useful for exercising
  behavior that isn't a simple pass/fail shell command, at the cost of
  being slower, LLM-dependent, and less reproducible than the other two.
"""
from __future__ import annotations

import logging

from kaizen.adapters.base import ProjectAdapter
from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalCase, EvalSuite
from kaizen.trace.store import ErrorInfo, TraceRecord, TraceStore

logger = logging.getLogger(__name__)


class RunnerAgent:
    """Runs every case in an eval suite against a target project."""

    def __init__(
        self,
        config: KaizenConfig,
        adapter: ProjectAdapter,
        trace_store: TraceStore,
        prompt_version: str | None = None,
        tool_schema_version: str | None = None,
    ):
        self.config = config
        self.adapter = adapter
        self.trace_store = trace_store
        self.prompt_version = prompt_version
        self.tool_schema_version = tool_schema_version

    def run_suite(self, suite: EvalSuite) -> list[TraceRecord]:
        records = [self.run_case(case) for case in suite.cases]
        return records

    def run_case(self, case: EvalCase) -> TraceRecord:
        if case.command is not None:
            record = self._run_command_case(case)
        elif case.mcp_tool_call is not None:
            record = self._run_mcp_tool_call_case(case)
        elif case.task_prompt is not None:
            record = self._run_task_case(case)
        else:
            raise ValueError(
                f"Eval case {case.id!r} has none of 'command', 'mcp_tool_call', or 'task_prompt'"
            )
        self.trace_store.append(record)
        return record

    def _run_command_case(self, case: EvalCase) -> TraceRecord:
        assert case.command is not None  # caller only dispatches here for command cases
        result = self.adapter.run(case.command)
        errors = self.adapter.parse_errors(result)
        success = result.exit_code == case.expect_exit_code and all(
            needle in (result.stdout + result.stderr) for needle in case.expect_output_contains
        )
        return TraceRecord(
            case_id=case.id,
            project_name=self.config.project_name,
            prompt_version=self.prompt_version,
            tool_schema_version=self.tool_schema_version,
            command=case.command,
            exit_code=result.exit_code,
            success=success,
            stdout=result.stdout,
            stderr=result.stderr,
            errors=errors if not success else [],
        )

    def _run_mcp_tool_call_case(self, case: EvalCase) -> TraceRecord:
        """Make one scripted MCP tool call - no LLM, no agent reasoning -
        and check the raw result deterministically."""
        assert case.mcp_tool_call is not None  # caller only dispatches here for mcp_tool_call cases
        if self.config.mcp_server is None:
            raise ValueError(
                f"Eval case {case.id!r} uses mcp_tool_call but no mcp_server is configured "
                f"in kaizen.yaml for project {self.config.project_name!r}"
            )
        import anyio

        from kaizen.mcp_client import call_tool

        outcome = anyio.run(
            call_tool,
            self.config.mcp_server,
            case.mcp_tool_call.tool,
            case.mcp_tool_call.arguments,
            case.timeout_seconds,
        )
        success = outcome.is_error == case.expect_is_error and all(
            needle in outcome.text for needle in case.expect_output_contains
        )
        errors = [] if success else [ErrorInfo(message=outcome.text[:2000], raw=outcome.text)]
        return TraceRecord(
            case_id=case.id,
            project_name=self.config.project_name,
            prompt_version=self.prompt_version,
            tool_schema_version=self.tool_schema_version,
            command=None,
            exit_code=0 if success else 1,
            success=success,
            stdout=outcome.text,
            stderr="",
            errors=errors,
        )

    def _run_task_case(self, case: EvalCase) -> TraceRecord:
        """Run a natural-language task against the target's MCP server.

        Imported lazily so that command-only setups don't require the
        Claude Agent SDK (and its bundled CLI) to be installed.
        """
        import anyio

        from kaizen.runner.mcp_task import run_mcp_task

        output_text, success, raw_errors = anyio.run(
            run_mcp_task, case, self.config
        )
        errors = [] if success else [ErrorInfo(message=output_text[:2000], raw=output_text)]
        return TraceRecord(
            case_id=case.id,
            project_name=self.config.project_name,
            prompt_version=self.prompt_version,
            tool_schema_version=self.tool_schema_version,
            command=None,
            exit_code=0 if success else 1,
            success=success,
            stdout=output_text,
            stderr="",
            errors=errors,
        )
