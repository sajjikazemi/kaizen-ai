"""Command-line entry point for KaizenAI."""
from __future__ import annotations

import subprocess

import click
from rich.console import Console
from rich.table import Table

from kaizen.adapters.dotnet import DotnetAdapter
from kaizen.baseline.store import BaselineSnapshot, BaselineStore
from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalSuite
from kaizen.evaluate.control_sampler import ControlSampler
from kaizen.evaluate.report_view import render_report
from kaizen.evaluate.split_report import evaluate as run_evaluation
from kaizen.fixer.agent import FixerAgent
from kaizen.runner.agent import RunnerAgent
from kaizen.trace.store import TraceStore

console = Console()


def _load(config_path: str):
    config = KaizenConfig.load(config_path)
    suite = EvalSuite.load(
        config.eval_suite_path if _is_abs_like(config.eval_suite_path) else
        f"{config.repo_path}/{config.eval_suite_path}"
    )
    adapter = DotnetAdapter(config.repo_path)
    trace_store = TraceStore(f"{config.repo_path}/{config.trace_store_path}")
    return config, suite, adapter, trace_store


def _is_abs_like(path: str) -> bool:
    return path.startswith("/") or (len(path) > 1 and path[1] == ":")


def _git_sha(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _baseline_store(config: KaizenConfig) -> BaselineStore:
    return BaselineStore(f"{config.repo_path}/.kaizen/baseline.json")


def _control_sampler(config: KaizenConfig) -> ControlSampler:
    return ControlSampler(f"{config.repo_path}/.kaizen/control_sample_history.json")


@click.group()
def main():
    """KaizenAI: closed-loop, self-improving agent framework."""


@main.command()
@click.option("--config", "config_path", required=True, help="Path to kaizen.yaml")
def run(config_path: str):
    """Run the eval suite against a target project and record failures."""
    config, suite, adapter, trace_store = _load(config_path)
    runner = RunnerAgent(config, adapter, trace_store)
    records = runner.run_suite(suite)

    table = Table(title=f"Kaizen run: {config.project_name}")
    table.add_column("Case")
    table.add_column("Result")
    for r in records:
        table.add_row(r.case_id, "[green]PASS[/]" if r.success else "[red]FAIL[/]")
    console.print(table)

    failures = [r for r in records if not r.success]
    if failures:
        console.print(f"[yellow]{len(failures)} failing case(s). Run `kaizen fix` to propose patches.[/]")


@main.command()
@click.option("--config", "config_path", required=True, help="Path to kaizen.yaml")
def baseline(config_path: str):
    """Run the FULL eval suite once and cache it as the ground-truth baseline.

    Refresh on a cadence (nightly / pre-merge-to-main) - not on every fix.
    """
    config, suite, adapter, trace_store = _load(config_path)
    runner = RunnerAgent(config, adapter, trace_store)
    records = runner.run_suite(suite)
    results = {r.case_id: r.success for r in records}

    sha = _git_sha(config.repo_path)
    snapshot = BaselineSnapshot(git_sha=sha, project_name=config.project_name, results=results)
    _baseline_store(config).save(snapshot)

    passed = sum(results.values())
    console.print(f"[green]Baseline saved[/] for {sha[:8]}: {passed}/{len(results)} cases passing.")


@main.command()
@click.option("--config", "config_path", required=True, help="Path to kaizen.yaml")
@click.option(
    "--failing", "failing_case_ids", required=True,
    help="Comma-separated case IDs that triggered this fix (the treatment seed)",
)
def evaluate(config_path: str, failing_case_ids: str):
    """Evaluate the currently checked-out candidate against the cached baseline.

    Builds a treatment split (failing cases + same-tag cases) and a
    stratified control split, runs both, and applies the McNemar-based
    fix/trade/reject decision rule.
    """
    config, suite, adapter, _trace_store = _load(config_path)
    snapshot = _baseline_store(config).latest()
    if snapshot is None:
        console.print("[red]No baseline snapshot found. Run `kaizen baseline` first.[/]")
        raise SystemExit(1)

    report = run_evaluation(
        config=config,
        adapter=adapter,
        suite=suite,
        failing_case_ids=set(failing_case_ids.split(",")),
        baseline_results=snapshot.results,
        control_sampler=_control_sampler(config),
    )
    console.print(render_report(report))
    return report


@main.command()
@click.option("--config", "config_path", required=True, help="Path to kaizen.yaml")
@click.option("--open-pr/--no-open-pr", default=False, help="Open a PR for each proposed fix")
def fix(config_path: str, open_pr: bool):
    """Analyze the latest failures, propose patches, and evaluate each one
    with the treatment/control gate before any PR is opened."""
    config, suite, adapter, trace_store = _load(config_path)
    failures = trace_store.read_failures()
    if not failures:
        console.print("[green]No recorded failures to fix.[/]")
        return

    snapshot = _baseline_store(config).latest()
    if snapshot is None:
        console.print("[red]No baseline snapshot found. Run `kaizen baseline` first.[/]")
        raise SystemExit(1)

    by_case = {}
    for r in failures:
        by_case[r.case_id] = r  # keep most recent failure per case
    case_commands = {c.id: c.command for c in suite.cases}

    fixer = FixerAgent(config, adapter)
    for case_id, record in by_case.items():
        console.print(f"[cyan]Proposing fix for {case_id}...[/]")
        plan = fixer.propose_fix(record)
        plan = fixer.verify(plan, case_commands.get(case_id))
        console.print(
            f"  tier={plan.highest_tier.value} verified_fixed={plan.verified_fixed} "
            f"files={plan.files_touched}"
        )

        report = run_evaluation(
            config=config,
            adapter=adapter,
            suite=suite,
            failing_case_ids={case_id},
            baseline_results=snapshot.results,
            control_sampler=_control_sampler(config),
        )
        console.print(render_report(report))

        if report.verdict == "rejected":
            console.print("  [red]Rejected:[/] no significant gain on treatment. Branch left for inspection.")
            continue

        plan.verdict = report.verdict
        if report.verdict == "trade":
            console.print("  [yellow]Trade detected (control regressed) - PR will flag this for explicit review.[/]")

        if open_pr:
            from kaizen.gate.pr_gate import open_pr as _open_pr

            url = _open_pr(config, plan)
            console.print(f"  [blue]PR opened:[/] {url}")


if __name__ == "__main__":
    main()
