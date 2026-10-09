"""Runner agent: executes a project's eval suite and records failures.

Two kinds of eval cases are supported:

* ``command`` cases - deterministic shell commands (``dotnet build``,
  ``dotnet test``). These don't need an LLM at all; the adapter runs them
  and parses structured errors directly. Cheap and fast - prefer these.
* ``task_prompt`` cases - natural-language tasks handed to Claude over the
  target project's MCP server (e.g. "add a customer record via the
  provisioning API and confirm it appears"). Useful for exercising
  behavior that isn't a simple pass/fail shell command.
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
        elif case.task_prompt is not None:
            record = self._run_task_case(case)
        else:
            raise ValueError(f"Eval case {case.id!r} has neither 'command' nor 'task_prompt'")
        self.trace_store.append(record)
        return record

    def _run_command_case(self, case: EvalCase) -> TraceRecord:
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
