import json

from kaizen.trace.store import TraceRecord, TraceStore


def test_trace_store_roundtrip(tmp_path):
    store = TraceStore(tmp_path / "traces.jsonl")
    rec = TraceRecord(case_id="c1", project_name="p", success=False, exit_code=1)
    store.append(rec)

    loaded = store.read_all()
    assert len(loaded) == 1
    assert loaded[0].case_id == "c1"

    failures = store.read_failures()
    assert len(failures) == 1

    # file is valid JSONL
    lines = (tmp_path / "traces.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    json.loads(lines[0])
