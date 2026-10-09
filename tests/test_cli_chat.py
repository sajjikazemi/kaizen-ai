import pytest

from kaizen.cli import _resolve_chat_case_id
from kaizen.trace.store import TraceRecord, TraceStore


def test_resolve_chat_case_id_returns_explicit_case_id_unchanged(tmp_path):
    store = TraceStore(tmp_path / "traces.jsonl")
    assert _resolve_chat_case_id(store, "explicit-case") == "explicit-case"


def test_resolve_chat_case_id_auto_picks_single_failure(tmp_path):
    store = TraceStore(tmp_path / "traces.jsonl")
    store.append(TraceRecord(case_id="only-one", project_name="p", success=False))
    assert _resolve_chat_case_id(store, None) == "only-one"


def test_resolve_chat_case_id_errors_when_no_failures(tmp_path):
    store = TraceStore(tmp_path / "traces.jsonl")
    with pytest.raises(SystemExit):
        _resolve_chat_case_id(store, None)


def test_resolve_chat_case_id_prompts_when_multiple_failures(tmp_path, monkeypatch):
    store = TraceStore(tmp_path / "traces.jsonl")
    store.append(TraceRecord(case_id="case-a", project_name="p", success=False))
    store.append(TraceRecord(case_id="case-b", project_name="p", success=False))

    import kaizen.cli as cli_module

    monkeypatch.setattr(cli_module.console, "input", lambda *_args, **_kwargs: "2")
    result = _resolve_chat_case_id(store, None)
    assert result in ("case-a", "case-b")  # whichever sorts second
