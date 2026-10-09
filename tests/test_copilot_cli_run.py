import json

from kaizen.copilot_cli.run import CopilotCliNotFound, _parse_jsonl, run_copilot_prompt


def _sample_jsonl() -> str:
    lines = [
        {"type": "session.tools_updated", "data": {"model": "claude-sonnet-5.5"}},
        {
            "type": "assistant.message",
            "data": {"messageId": "m1", "content": "OK"},
        },
        {
            "type": "session.mcp_server_status_changed",
            "data": {"serverName": "flaky-server", "status": "failed", "error": "connection refused"},
        },
        {
            "type": "result",
            "timestamp": "2026-10-09T17:04:12.327Z",
            "sessionId": "ab1ee887-e67b-482f-a65d-8c011a7a1778",
            "exitCode": 0,
        },
    ]
    return "\n".join(json.dumps(line) for line in lines)


def test_parse_jsonl_extracts_text_session_and_errors():
    text, exit_code, session_id, tool_errors, events = _parse_jsonl(_sample_jsonl())
    assert text == "OK"
    assert exit_code == 0
    assert session_id == "ab1ee887-e67b-482f-a65d-8c011a7a1778"
    assert len(tool_errors) == 1
    assert "flaky-server" in tool_errors[0]
    assert len(events) == 4


def test_parse_jsonl_ignores_blank_and_malformed_lines():
    stdout = '\n{"type": "assistant.message", "data": {"messageId": "m1", "content": "hi"}}\n\nnot json\n'
    text, exit_code, session_id, tool_errors, events = _parse_jsonl(stdout)
    assert text == "hi"
    assert exit_code is None
    assert session_id is None
    assert tool_errors == []
    assert len(events) == 1


def test_run_copilot_prompt_raises_clear_error_when_cli_missing(tmp_path, monkeypatch):
    import subprocess

    def fake_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", fake_run)
    try:
        run_copilot_prompt("hi", cwd=str(tmp_path))
        raised = False
    except CopilotCliNotFound:
        raised = True
    assert raised
