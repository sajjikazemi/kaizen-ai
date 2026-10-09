"""Builds the treatment/control split evaluation report.

Treatment = the failing case(s) that triggered the fix, plus any other case
sharing a tag with them (same feature area - a proxy for "this code path").
Control = a stratified sample of everything else, rotated across cycles.

Decision rule:
  - significant gain on treatment + control not significantly worse -> FIX
  - significant gain on treatment + control significantly worse    -> TRADE
  - no significant gain on treatment                               -> REJECTED
"""
from __future__ import annotations

from dataclasses import dataclass

from kaizen.adapters.base import ProjectAdapter
from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalCase, EvalSuite
from kaizen.evaluate.control_sampler import ControlSampler
from kaizen.evaluate.mcnemar import McNemarResult, build_contingency_table, mcnemar_test
from kaizen.runner.agent import RunnerAgent
from kaizen.trace.store import TraceStore


@dataclass
class SplitResult:
    name: str  # "treatment" | "control"
    case_ids: list[str]
    baseline_results: dict[str, bool]
    candidate_results: dict[str, bool]
    mcnemar: McNemarResult


@dataclass
class EvaluationReport:
    treatment: SplitResult
    control: SplitResult
    verdict: str  # "fix" | "trade" | "rejected"


def build_treatment_split(suite: EvalSuite, failing_case_ids: set[str]) -> list[EvalCase]:
    failing_tags = {tag for case in suite.cases if case.id in failing_case_ids for tag in case.tags}
    return [
        case
        for case in suite.cases
        if case.id in failing_case_ids or (failing_tags & set(case.tags))
    ]


def _run_cases(cases: list[EvalCase], config: KaizenConfig, adapter: ProjectAdapter) -> dict[str, bool]:
    scratch_store = TraceStore(f"{config.repo_path}/.kaizen/_evaluate_scratch.jsonl")
    runner = RunnerAgent(config, adapter, scratch_store)
    return {case.id: runner.run_case(case).success for case in cases}


def evaluate(
    config: KaizenConfig,
    adapter: ProjectAdapter,
    suite: EvalSuite,
    failing_case_ids: set[str],
    baseline_results: dict[str, bool],
    control_sampler: ControlSampler,
    alpha: float = 0.05,
) -> EvaluationReport:
    """Evaluates the CURRENTLY CHECKED-OUT candidate state against `baseline_results`.

    Caller is responsible for making sure the repo at `config.repo_path` is
    checked out onto the candidate branch/patch before calling this.
    """
    treatment_cases = build_treatment_split(suite, failing_case_ids)
    treatment_ids = {c.id for c in treatment_cases}
    non_treatment = [c for c in suite.cases if c.id not in treatment_ids]
    control_cases = control_sampler.sample(non_treatment)

    treatment_candidate = _run_cases(treatment_cases, config, adapter)
    control_candidate = _run_cases(control_cases, config, adapter)

    treatment_case_ids = list(treatment_candidate)
    control_case_ids = list(control_candidate)

    treatment_table = build_contingency_table(baseline_results, treatment_candidate, treatment_case_ids)
    control_table = build_contingency_table(baseline_results, control_candidate, control_case_ids)

    treatment_mcnemar = mcnemar_test(treatment_table, alpha)
    control_mcnemar = mcnemar_test(control_table, alpha)

    treatment_split = SplitResult(
        name="treatment",
        case_ids=treatment_case_ids,
        baseline_results={cid: baseline_results.get(cid, False) for cid in treatment_case_ids},
        candidate_results=treatment_candidate,
        mcnemar=treatment_mcnemar,
    )
    control_split = SplitResult(
        name="control",
        case_ids=control_case_ids,
        baseline_results={cid: baseline_results.get(cid, False) for cid in control_case_ids},
        candidate_results=control_candidate,
        mcnemar=control_mcnemar,
    )

    if treatment_mcnemar.direction == "gain" and control_mcnemar.direction != "loss":
        verdict = "fix"
    elif treatment_mcnemar.direction == "gain" and control_mcnemar.direction == "loss":
        verdict = "trade"
    else:
        verdict = "rejected"

    return EvaluationReport(treatment=treatment_split, control=control_split, verdict=verdict)
