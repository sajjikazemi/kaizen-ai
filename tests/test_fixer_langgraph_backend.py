from dataclasses import dataclass
from typing import Any

from kaizen.fixer.backends.langgraph_backend import _requires_code_review


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
