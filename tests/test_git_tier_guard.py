import subprocess

import pytest

from kaizen.fixer.git_tier_guard import changed_files, revert_locked_paths


def _run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _run(["git", "init", "-q"], cwd=repo_path)
    _run(["git", "config", "user.email", "t@t.com"], cwd=repo_path)
    _run(["git", "config", "user.name", "t"], cwd=repo_path)
    (repo_path / "infra").mkdir()
    (repo_path / "infra" / "main.tf").write_text("ORIGINAL")
    (repo_path / "Program.cs").write_text("original code")
    _run(["git", "add", "-A"], cwd=repo_path)
    _run(["git", "commit", "-q", "-m", "base"], cwd=repo_path)
    return repo_path


def test_changed_files_includes_tracked_and_untracked(repo):
    (repo / "Program.cs").write_text("modified code")
    (repo / "new_file.cs").write_text("new")
    files = changed_files(str(repo), "HEAD")
    assert set(files) == {"Program.cs", "new_file.cs"}


def test_revert_locked_paths_reverts_existing_tier3_file(repo):
    (repo / "infra" / "main.tf").write_text("MALICIOUS CHANGE")
    (repo / "Program.cs").write_text("legit fix")

    surviving = revert_locked_paths(str(repo), "HEAD")

    assert (repo / "infra" / "main.tf").read_text() == "ORIGINAL"
    assert surviving == ["Program.cs"]


def test_revert_locked_paths_deletes_newly_created_tier3_file(repo):
    (repo / "infra").mkdir(exist_ok=True)
    (repo / "infra" / "new_secret.pem").write_text("should not exist")

    surviving = revert_locked_paths(str(repo), "HEAD")

    assert not (repo / "infra" / "new_secret.pem").exists()
    assert surviving == []
