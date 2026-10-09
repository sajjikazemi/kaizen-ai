from kaizen.evals.schema import EvalCase
from kaizen.evaluate.control_sampler import ControlSampler


def _cases(tag: str, n: int) -> list[EvalCase]:
    return [EvalCase(id=f"{tag}-{i}", command=["true"], tags=[tag]) for i in range(n)]


def test_sample_respects_fraction_per_stratum(tmp_path):
    sampler = ControlSampler(tmp_path / "state.json", sample_fraction=0.5, min_per_stratum=1)
    cases = _cases("auth", 4) + _cases("billing", 4)
    selected = sampler.sample(cases)
    # 50% of each 4-case stratum -> 2 + 2
    assert len(selected) == 4


def test_sample_rotates_across_cycles(tmp_path):
    sampler = ControlSampler(tmp_path / "state.json", sample_fraction=0.25, min_per_stratum=1)
    cases = _cases("auth", 4)

    first = {c.id for c in sampler.sample(cases)}
    second = {c.id for c in sampler.sample(cases)}
    # With rotation, the least-recently-sampled case should change between
    # cycles rather than always returning the same one.
    assert first != second or len(cases) == 1


def test_sample_respects_min_per_stratum(tmp_path):
    sampler = ControlSampler(tmp_path / "state.json", sample_fraction=0.01, min_per_stratum=1)
    cases = _cases("auth", 10)
    selected = sampler.sample(cases)
    assert len(selected) == 1
