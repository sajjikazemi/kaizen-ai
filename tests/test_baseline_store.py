from kaizen.baseline.store import BaselineSnapshot, BaselineStore


def test_baseline_store_roundtrip(tmp_path):
    store = BaselineStore(tmp_path / "baseline.json")
    snap = BaselineSnapshot(git_sha="abc123", project_name="p", results={"c1": True, "c2": False})
    store.save(snap)

    loaded = store.load("abc123")
    assert loaded is not None
    assert loaded.results == {"c1": True, "c2": False}

    latest = store.latest()
    assert latest.git_sha == "abc123"

    assert store.load("missing") is None


def test_baseline_store_latest_picks_most_recent(tmp_path):
    store = BaselineStore(tmp_path / "baseline.json")
    store.save(BaselineSnapshot(git_sha="old", project_name="p", results={}, created_at=1.0))
    store.save(BaselineSnapshot(git_sha="new", project_name="p", results={}, created_at=2.0))
    assert store.latest().git_sha == "new"
