import subprocess
from unittest.mock import patch

from kaizen.config import KaizenConfig, PatchTier
from kaizen.fixer.agent import PatchPlan
from kaizen.gate.pr_gate import _pr_create_url_fallback, open_pr


def _plan() -> PatchPlan:
    return PatchPlan(
        case_id="c1", branch_name="kaizen/fix/c1", summary="Fix c1",
        files_touched=["a.cs"], highest_tier=PatchTier.TIER_2_CODE, verified_fixed=True,
    )


def _config() -> KaizenConfig:
    return KaizenConfig(project_name="p", repo_path="/repo")


def test_pr_create_url_fallback_from_ssh_remote(tmp_path):
    with patch("subprocess.run") as run:
        run.return_value.stdout = "git@github.com:octo-org/sample-app.git\n"
        url = _pr_create_url_fallback("/repo", "kaizen/fix/c1")
    assert url == "https://github.com/octo-org/sample-app/pull/new/kaizen/fix/c1"


def test_pr_create_url_fallback_from_https_remote():
    with patch("subprocess.run") as run:
        run.return_value.stdout = "https://github.com/octo-org/sample-app.git\n"
        url = _pr_create_url_fallback("/repo", "kaizen/fix/c1")
    assert url == "https://github.com/octo-org/sample-app/pull/new/kaizen/fix/c1"


def test_open_pr_falls_back_to_url_when_gh_cli_missing():
    call_count = {"n": 0}

    def fake_run(args, **kwargs):
        call_count["n"] += 1
        if args[:2] == ["gh", "pr"]:
            raise FileNotFoundError("gh not found")
        if args[:2] == ["git", "remote"]:
            result = type("R", (), {})()
            result.stdout = "git@github.com:octo-org/sample-app.git\n"
            return result
        return type("R", (), {"stdout": "", "returncode": 0})()

    with patch("subprocess.run", side_effect=fake_run):
        result = open_pr(_config(), _plan())

    assert "https://github.com/octo-org/sample-app/pull/new/kaizen/fix/c1" in result
    assert "not installed" in result


def test_open_pr_falls_back_to_url_when_gh_pr_create_fails():
    def fake_run(args, **kwargs):
        if args[:2] == ["gh", "pr"]:
            raise subprocess.CalledProcessError(1, args, stderr="not authenticated")
        if args[:2] == ["git", "remote"]:
            result = type("R", (), {})()
            result.stdout = "git@github.com:octo-org/sample-app.git\n"
            return result
        return type("R", (), {"stdout": "", "returncode": 0})()

    with patch("subprocess.run", side_effect=fake_run):
        result = open_pr(_config(), _plan())

    assert "https://github.com/octo-org/sample-app/pull/new/kaizen/fix/c1" in result
    assert "not authenticated" in result
