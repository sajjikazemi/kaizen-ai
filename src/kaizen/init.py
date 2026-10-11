"""Scaffolds a starter `kaizen.yaml` (+ one catch-all eval case) for a
target project.

Detection is intentionally shallow and conservative: it picks an adapter
from a handful of well-known project markers directly under the target
path, and writes a single eval case that runs the whole test suite. This
is a starting point to edit, not a replacement for curating a real,
tagged eval suite - see the README's "Adding a new target project"
section for that. In particular, `model.backend` here always defaults to
`copilot_cli` (no API key required to try it) and `gate.base_branch` is
best-effort detected from git, falling back to "main".
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

_ADAPTER_TEST_COMMAND: dict[str, list[str]] = {
    "pytest": ["pytest"],
    "dotnet": ["dotnet", "test"],
}

_PYTEST_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "pytest.ini")


def detect_adapter(path: Path) -> str | None:
    """Best-effort adapter detection from well-known project files
    directly under `path`. Returns None if nothing recognizable is found."""
    if not path.is_dir():
        return None
    if any(path.glob("*.csproj")) or any(path.glob("*.sln")):
        return "dotnet"
    names = {p.name for p in path.iterdir()}
    if set(_PYTEST_MARKERS) & names:
        return "pytest"
    return None


def detect_default_branch(path: Path) -> str:
    """Best-effort: the remote's default branch, falling back to the
    current branch, falling back to "main" (e.g. outside a git repo)."""
    for args in (
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    ):
        result = subprocess.run(args, cwd=path, capture_output=True, text=True)
        ref = result.stdout.strip()
        if result.returncode == 0 and ref and ref != "HEAD":
            return ref.rsplit("/", 1)[-1]
    return "main"


def scaffold(path: Path, adapter: str, project_name: str | None = None) -> Path:
    """Writes `kaizen.yaml` + `evals/tests-pass.eval.yaml` under `path`.
    Caller is responsible for checking kaizen.yaml doesn't already exist
    (or that overwriting it is wanted) before calling this. Returns the
    written kaizen.yaml path."""
    resolved = path.resolve()
    project_name = project_name or resolved.name

    evals_dir = path / "evals"
    evals_dir.mkdir(exist_ok=True)
    eval_case = {
        "id": "tests-pass",
        "description": "The full test suite passes.",
        "command": _ADAPTER_TEST_COMMAND[adapter],
        "expect_exit_code": 0,
    }
    (evals_dir / "tests-pass.eval.yaml").write_text(
        yaml.safe_dump(eval_case, sort_keys=False), encoding="utf-8"
    )

    config = {
        "project_name": project_name,
        "repo_path": str(resolved),
        "eval_suite_path": "evals",
        "adapter": {"name": adapter},
        "gate": {
            "base_branch": detect_default_branch(path),
            "branch_prefix": "kaizen/fix",
            "require_review_for": ["tier_2_code", "tier_3_locked"],
            "auto_apply_tiers": [],
        },
        "model": {
            "backend": "copilot_cli",
            "copilot_runner_model": None,
            "copilot_fixer_model": None,
        },
        "trace_store_path": ".kaizen/traces.jsonl",
    }
    header = (
        "# Scaffolded by `kaizen init` - a starting point, not a finished eval\n"
        "# suite. One catch-all case runs the whole test suite; add tagged,\n"
        "# more targeted cases as you go (see the README's \"Adding a new\n"
        "# target project\" section). model.backend defaults to copilot_cli\n"
        "# (no API key needed) - switch to langgraph once you have one.\n"
    )
    kaizen_yaml = path / "kaizen.yaml"
    kaizen_yaml.write_text(header + yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return kaizen_yaml
