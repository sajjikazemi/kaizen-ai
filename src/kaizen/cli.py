"""Command-line entry point for KaizenAI."""
from __future__ import annotations

import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from kaizen.adapters import get_adapter
from kaizen.baseline.store import BaselineSnapshot, BaselineStore
from kaizen.config import KaizenConfig, PatchTier
from kaizen.evals.schema import EvalSuite
from kaizen.evaluate.control_sampler import ControlSampler
from kaizen.evaluate.report_view import render_report
from kaizen.evaluate.split_report import evaluate as run_evaluation
from kaizen.fixer.agent import FixerAgent, PatchPlan, build_fix_prompt
from kaizen.fixer.errors import FixerSessionError
from kaizen.fixer.tiering import classify_tier
from kaizen.runner.agent import RunnerAgent
from kaizen.trace.store import TraceStore

console = Console()


def _load(config_path: str):
    config = KaizenConfig.load(config_path)
    suite = EvalSuite.load(
        config.eval_suite_path if _is_abs_like(config.eval_suite_path) else
        f"{config.repo_path}/{config.eval_suite_path}"
    )
    adapter = get_adapter(config)
    trace_store = TraceStore(f"{config.repo_path}/{config.trace_store_path}")
    return config, suite, adapter, trace_store


def _is_abs_like(path: str) -> bool:
    return path.startswith("/") or (len(path) > 1 and path[1] == ":")


def _debug_enabled() -> bool:
    import os

    return os.environ.get("KAIZEN_DEBUG", "").lower() in ("1", "true", "yes")


def _git_sha(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _abandon_branch(config: KaizenConfig) -> None:
    """Best-effort cleanup: return the repo to its base branch after a
    Fixer session fails, so a crash doesn't leave the working tree stuck
    on a half-finished fix branch."""
    subprocess.run(
        ["git", "checkout", config.gate.base_branch],
        cwd=config.repo_path, capture_output=True, text=True,
    )


def _baseline_store(config: KaizenConfig) -> BaselineStore:
    return BaselineStore(f"{config.repo_path}/.kaizen/baseline.json")


def _control_sampler(config: KaizenConfig) -> ControlSampler:
    return ControlSampler(f"{config.repo_path}/.kaizen/control_sample_history.json")


@click.group(invoke_without_command=True)
@click.option("--config", "config_path", default=None, help="Path to kaizen.yaml (defaults to ./kaizen.yaml)")
@click.option(
    "--case", "case_id", default=None,
    help="Eval case to chat about (auto-picked if there's exactly one failing case)",
)
@click.pass_context
def main(ctx: click.Context, config_path: str | None, case_id: str | None):
    """KaizenAI: closed-loop, self-improving agent framework.

    Run with no subcommand (just `kaizen`) to open an interactive chat
    session for a failing case - like `copilot`/`claude` - instead of the
    one-shot `run`/`baseline`/`fix`/`evaluate` commands below.
    """
    if ctx.invoked_subcommand is not None:
        return
    _interactive_chat(config_path, case_id)


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
        try:
            plan = fixer.propose_fix(record)
        except FixerSessionError as exc:
            console.print(f"  [red]Fixer session failed:[/] {exc}")
            console.print("  [yellow]Branch abandoned; returning to base branch. Set KAIZEN_DEBUG=1 for the full trace.[/]")
            if _debug_enabled():
                console.print_exception()
            _abandon_branch(config)
            continue
        except Exception as exc:  # noqa: BLE001 - last-resort guard, never show a raw traceback by default
            console.print(f"  [red]Unexpected error proposing fix:[/] {exc}")
            if _debug_enabled():
                console.print_exception()
            else:
                console.print("  [dim]Set KAIZEN_DEBUG=1 to see the full traceback.[/]")
            _abandon_branch(config)
            continue

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


def _resolve_chat_case_id(trace_store: TraceStore, case_id: str | None) -> str:
    if case_id is not None:
        return case_id
    failures = trace_store.read_failures()
    case_ids = sorted({r.case_id for r in failures})
    if not case_ids:
        console.print("[yellow]No failing cases recorded yet. Run `kaizen run` first, or pass --case <id>.[/]")
        raise SystemExit(1)
    if len(case_ids) == 1:
        return case_ids[0]
    console.print("[cyan]Multiple failing cases - pick one:[/]")
    for i, cid in enumerate(case_ids, 1):
        console.print(f"  {i}. {cid}")
    choice = console.input("> ").strip()
    try:
        return case_ids[int(choice) - 1]
    except (ValueError, IndexError):
        console.print("[red]Invalid choice.[/]")
        raise SystemExit(1) from None


def _ensure_fix_branch(config: KaizenConfig, branch_name: str) -> None:
    exists = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        cwd=config.repo_path, capture_output=True,
    ).returncode == 0
    if exists:
        subprocess.run(["git", "checkout", branch_name], cwd=config.repo_path, check=True)
        console.print(f"[cyan]Resuming existing branch {branch_name}[/]")
    else:
        subprocess.run(
            ["git", "checkout", "-b", branch_name, config.gate.base_branch],
            cwd=config.repo_path, check=True,
        )
        console.print(f"[cyan]Created branch {branch_name}[/]")


def _interactive_chat(config_path: str | None, case_id: str | None) -> None:
    """Drops into a REPL for a single failing case's Fixer session - the
    `kaizen fix` flow, but conversational: send follow-up messages, ask it
    to try a different approach, inspect the diff, verify, or open the PR
    whenever you're satisfied, all in the same continuing session."""
    import anyio

    from kaizen.fixer.dispatch import open_chat_session, session_id_for
    from kaizen.gate.pr_gate import open_pr as _open_pr

    if not config_path:
        default_path = Path("kaizen.yaml")
        if not default_path.exists():
            console.print(
                "[red]No kaizen.yaml in the current directory.[/] "
                "Pass --config <path>, or cd into a project that has one."
            )
            raise SystemExit(1)
        config_path = str(default_path)

    config, suite, adapter, trace_store = _load(config_path)
    case_id = _resolve_chat_case_id(trace_store, case_id)

    case = next((c for c in suite.cases if c.id == case_id), None)
    if case is None:
        console.print(f"[red]No eval case {case_id!r} found in the suite.[/]")
        raise SystemExit(1)

    records = [r for r in trace_store.read_all() if r.case_id == case_id]
    if not records:
        console.print(f"[red]No trace recorded yet for {case_id!r}. Run `kaizen run` first.[/]")
        raise SystemExit(1)
    record = records[-1]

    branch_name = f"{config.gate.branch_prefix}/{case_id}"
    _ensure_fix_branch(config, branch_name)

    session = open_chat_session(config, session_id_for(record))
    console.print(
        f"[bold cyan]Kaizen chat[/] - case [bold]{case_id}[/], branch {branch_name}. "
        "Type /help for commands, /exit to leave.\n"
    )

    async def _run() -> None:
        touched: list[str] = []
        console.print("[dim]Sending initial failure context...[/]")
        try:
            touched = await session.send(build_fix_prompt(record))
        except FixerSessionError as exc:
            console.print(f"  [red]Session error:[/] {exc}")
        if touched:
            console.print(f"  [green]Files touched so far:[/] {touched}")

        while True:
            user_input = console.input("\n[bold cyan]you>[/] ").strip()
            if not user_input:
                continue
            if user_input in ("/exit", "/quit"):
                console.print("[yellow]Leaving chat - branch left as-is; run `kaizen` again for this case to resume.[/]")
                return
            if user_input == "/abandon":
                _abandon_branch(config)
                console.print("[yellow]Branch abandoned; returned to base branch.[/]")
                return
            if user_input == "/diff":
                result = subprocess.run(
                    ["git", "diff", config.gate.base_branch], cwd=config.repo_path,
                    capture_output=True, text=True,
                )
                console.print(result.stdout or "[dim](no changes yet)[/]")
                continue
            if user_input == "/verify":
                if case.command:
                    result = adapter.run(case.command)
                    status = "[green]PASS[/]" if result.exit_code == 0 else "[red]FAIL[/]"
                    console.print(f"  verify: {status} (exit_code={result.exit_code})")
                else:
                    console.print("[dim]This case has no shell command to verify directly.[/]")
                continue
            if user_input == "/pr":
                tiers = [classify_tier(f) for f in touched] or [PatchTier.TIER_1_SAFE]
                plan = PatchPlan(
                    case_id=case_id, branch_name=branch_name,
                    summary=f"Fix for failing eval case '{case_id}'",
                    files_touched=touched,
                    highest_tier=max(tiers, key=lambda t: list(PatchTier).index(t)),
                )
                url = _open_pr(config, plan)
                console.print(f"[blue]PR opened:[/] {url}")
                continue
            if user_input in ("/help", "?"):
                console.print("Commands: /verify  /diff  /pr  /abandon  /exit")
                continue

            try:
                touched = await session.send(user_input)
            except FixerSessionError as exc:
                console.print(f"  [red]Session error:[/] {exc}")
                continue
            if touched:
                console.print(f"  [green]Files touched so far:[/] {touched}")

    anyio.run(_run)


if __name__ == "__main__":
    main()
