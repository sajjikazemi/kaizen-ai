from unittest.mock import patch

from kaizen.evals.schema import EvalCase, EvalSuite
from kaizen.evaluate import split_report
from kaizen.evaluate.control_sampler import ControlSampler


def _suite() -> EvalSuite:
    cases = [EvalCase(id="failing-1", command=["true"], tags=["feature-x"])]
    cases += [EvalCase(id=f"related-{i}", command=["true"], tags=["feature-x"]) for i in range(9)]
    cases += [EvalCase(id=f"other-{i}", command=["true"], tags=["feature-y"]) for i in range(10)]
    return EvalSuite(name="s", cases=cases)


def test_build_treatment_split_includes_same_tag_cases():
    suite = _suite()
    treatment = split_report.build_treatment_split(suite, {"failing-1"})
    ids = {c.id for c in treatment}
    assert ids == {"failing-1"} | {f"related-{i}" for i in range(9)}


def test_evaluate_returns_fix_when_treatment_gains_and_control_flat(tmp_path):
    suite = _suite()
    baseline_results = {f"related-{i}": False for i in range(9)}
    baseline_results["failing-1"] = False
    baseline_results.update({f"other-{i}": True for i in range(10)})

    def fake_run_cases(cases, config, adapter):
        # Everything in the candidate run passes (treatment recovers, control holds).
        return {c.id: True for c in cases}

    with patch.object(split_report, "_run_cases", side_effect=fake_run_cases):
        report = split_report.evaluate(
            config=None,
            adapter=None,
            suite=suite,
            failing_case_ids={"failing-1"},
            baseline_results=baseline_results,
            control_sampler=ControlSampler(tmp_path / "state.json", sample_fraction=1.0),
        )

    assert report.verdict == "fix"
    assert report.treatment.mcnemar.direction == "gain"
    assert report.control.mcnemar.direction == "flat"
