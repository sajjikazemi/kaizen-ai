from dataclasses import dataclass
from typing import Any

from kaizen.fixer.backends.langgraph_backend import (
    _describe_tool_call,
    _describe_tool_result,
    _print_progress,
    _requires_code_review,
)


@dataclass
class _FakeToolCallRequest:
    """Minimal stand-in for langchain's ToolCallRequest - only `.tool_call`
    is used by `_requires_code_review`."""

    tool_call: dict[str, Any]


def test_requires_code_review_true_for_application_code_path():
    req = _FakeToolCallRequest(tool_call={"name": "write_file", "args": {"path": "src/Program.cs"}})
    assert _requires_code_review(req) is True


def test_requires_code_review_false_for_tier1_safe_path():
    req = _FakeToolCallRequest(tool_call={"name": "write_file", "args": {"path": "README.md"}})
    assert _requires_code_review(req) is False


def test_requires_code_review_takes_single_argument():
    """Regression test: the `when` predicate passed to HumanInTheLoopMiddleware
    is called with exactly one ToolCallRequest-like argument, not
    (tool_call, state, runtime) - a real bug caught live against gpt-4o-reasoning."""
    req = _FakeToolCallRequest(tool_call={"name": "edit_file", "args": {"path": "x.cs"}})
    # Should not raise TypeError about missing arguments.
    _requires_code_review(req)


def test_describe_tool_call_is_natural_language_for_known_tools():
    assert _describe_tool_call("read_file", {"path": "a.cs"}) == "Reading a.cs"
    assert _describe_tool_call("write_file", {"path": "a.cs"}) == "Writing a.cs"
    assert _describe_tool_call("edit_file", {"path": "a.cs"}) == "Editing a.cs"
    assert _describe_tool_call("run_bash", {"command": "dotnet build"}) == "Running: dotnet build"


def test_describe_tool_call_falls_back_for_unknown_tool():
    assert _describe_tool_call("mystery_tool", {}) == "Calling mystery_tool"


def test_describe_tool_result_summarizes_exit_code_instead_of_dumping_output():
    assert _describe_tool_result("exit=0\nSTDOUT:\nlots of noisy output\n") == "done"
    assert _describe_tool_result("exit=1\nSTDOUT:\n...") == "failed (exit 1)"


def test_describe_tool_result_shows_denied_and_error_messages():
    assert "DENIED" in _describe_tool_result("DENIED: infra/main.tf is locked")
    assert "ERROR" in _describe_tool_result("ERROR: old_str not found in Program.cs")


@dataclass
class _FakeMessage:
    type: str
    content: Any = ""
    tool_calls: list[dict] | None = None


def test_print_progress_skips_human_echo(capsys):
    _print_progress(_FakeMessage(type="human", content="the full original prompt..."))
    assert capsys.readouterr().out == ""


def test_print_progress_prints_natural_language_for_tool_calls(capsys):
    _print_progress(
        _FakeMessage(type="ai", tool_calls=[{"name": "read_file", "args": {"path": "a.cs"}}])
    )
    out = capsys.readouterr().out
    assert "Reading a.cs" in out


def test_print_progress_summarizes_tool_results_instead_of_dumping_them(capsys):
    _print_progress(_FakeMessage(type="tool", content="exit=0\nSTDOUT:\n" + "x" * 5000))
    out = capsys.readouterr().out
    assert "done" in out
    assert "x" * 100 not in out  # the raw dump must not appear


def test_hitl_resume_payload_shape_matches_langchain_contract():
    """Regression test: a second real bug caught live against gpt-4o-reasoning -
    `interrupt(hitl_request)["decisions"]` means the resume value we send
    back MUST be a dict with a "decisions" key (a list, one entry per
    interrupted tool call, in order) - not a bare list. Confirmed by
    importing langchain's own HITLResponse TypedDict directly, so this
    breaks loudly if the library's contract ever changes.
    """
    from langchain.agents.middleware.human_in_the_loop import HITLResponse

    assert "decisions" in HITLResponse.__annotations__
