import pytest

from kaizen.adapters.dotnet import DotnetAdapter
from kaizen.config import KaizenConfig, McpServerConfig
from kaizen.evals.schema import EvalCase, McpToolCallSpec
from kaizen.mcp_client import ToolCallOutcome
from kaizen.runner.agent import RunnerAgent
from kaizen.trace.store import TraceStore


def _runner(tmp_path, mcp_server=None) -> RunnerAgent:
    config = KaizenConfig(project_name="p", repo_path=str(tmp_path), mcp_server=mcp_server)
    adapter = DotnetAdapter(str(tmp_path))  # unused by mcp_tool_call cases
    store = TraceStore(tmp_path / "traces.jsonl")
    return RunnerAgent(config, adapter, store)


def test_run_case_dispatches_unknown_case_raises(tmp_path):
    runner = _runner(tmp_path)
    with pytest.raises(ValueError, match="none of"):
        runner.run_case(EvalCase(id="x"))


def test_mcp_tool_call_requires_mcp_server_configured(tmp_path):
    runner = _runner(tmp_path)  # no mcp_server
    case = EvalCase(id="x", mcp_tool_call=McpToolCallSpec(tool="echo", arguments={}))
    with pytest.raises(ValueError, match="no mcp_server is configured"):
        runner.run_case(case)


def test_mcp_tool_call_success(tmp_path, monkeypatch):
    runner = _runner(tmp_path, mcp_server=McpServerConfig(command="echo"))
    case = EvalCase(
        id="echo-works",
        mcp_tool_call=McpToolCallSpec(tool="echo", arguments={"text": "hi"}),
        expect_output_contains=["hi"],
    )

    async def fake_call_tool(server, tool, arguments, timeout_seconds):
        assert tool == "echo"
        assert arguments == {"text": "hi"}
        return ToolCallOutcome(is_error=False, text="hi there")

    monkeypatch.setattr("kaizen.mcp_client.call_tool", fake_call_tool)

    record = runner.run_case(case)
    assert record.success is True
    assert record.case_id == "echo-works"
    assert record.stdout == "hi there"


def test_mcp_tool_call_fails_on_unexpected_error_flag(tmp_path, monkeypatch):
    runner = _runner(tmp_path, mcp_server=McpServerConfig(command="echo"))
    case = EvalCase(id="x", mcp_tool_call=McpToolCallSpec(tool="boom", arguments={}))

    async def fake_call_tool(server, tool, arguments, timeout_seconds):
        return ToolCallOutcome(is_error=True, text="boom")

    monkeypatch.setattr("kaizen.mcp_client.call_tool", fake_call_tool)

    record = runner.run_case(case)
    assert record.success is False
    assert record.errors[0].message == "boom"


def test_mcp_tool_call_expect_is_error_true(tmp_path, monkeypatch):
    runner = _runner(tmp_path, mcp_server=McpServerConfig(command="echo"))
    case = EvalCase(
        id="should-fail", mcp_tool_call=McpToolCallSpec(tool="boom", arguments={}), expect_is_error=True
    )

    async def fake_call_tool(server, tool, arguments, timeout_seconds):
        return ToolCallOutcome(is_error=True, text="boom")

    monkeypatch.setattr("kaizen.mcp_client.call_tool", fake_call_tool)

    record = runner.run_case(case)
    assert record.success is True
