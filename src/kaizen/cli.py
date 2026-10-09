"""Command-line entry point for KaizenAI."""
from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from kaizen.adapters.dotnet import DotnetAdapter
from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalSuite
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
@click.option("--open-pr/--no-open-pr", default=False, help="Open a PR for each proposed fix")
def fix(config_path: str, open_pr: bool):
    """Analyze the latest failures and propose patches (human review required)."""
    config, suite, adapter, trace_store = _load(config_path)
    failures = trace_store.read_failures()
    if not failures:
        console.print("[green]No recorded failures to fix.[/]")
        return

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
        if open_pr:
            from kaizen.gate.pr_gate import open_pr as _open_pr

            url = _open_pr(config, plan)
            console.print(f"  [blue]PR opened:[/] {url}")


if __name__ == "__main__":
    main()
