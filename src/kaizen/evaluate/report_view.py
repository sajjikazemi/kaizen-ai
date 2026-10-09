"""Renders an EvaluationReport as a rich table, matching the
"by split / baseline vs candidate / delta" format used for reporting to
stakeholders.
"""
from __future__ import annotations

from rich.table import Table

from kaizen.evaluate.split_report import EvaluationReport, SplitResult


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{100 * count / total:.1f}%"


def _row(table: Table, split: SplitResult) -> None:
    n = split.mcnemar.table.n
    baseline_correct = split.mcnemar.table.baseline_correct
    candidate_correct = split.mcnemar.table.candidate_correct
    delta_pts = 100 * (candidate_correct - baseline_correct) / n if n else 0.0
    delta_str = f"{delta_pts:+.1f}pts"
    table.add_row(
        split.name,
        f"{baseline_correct}/{n} ({_pct(baseline_correct, n)})",
        f"{candidate_correct}/{n} ({_pct(candidate_correct, n)})",
        delta_str,
        f"{split.mcnemar.p_value:.3f}",
        split.mcnemar.direction,
    )


def render_report(report: EvaluationReport) -> Table:
    table = Table(title=f"Kaizen evaluation - verdict: {report.verdict.upper()}")
    table.add_column("Split")
    table.add_column("Baseline Correct")
    table.add_column("Candidate Correct")
    table.add_column("\u0394 Correct")
    table.add_column("McNemar p")
    table.add_column("Direction")
    _row(table, report.treatment)
    _row(table, report.control)
    return table
