"""Stratified sampler for the control split.

Samples a representative subset of non-treatment cases rather than running
the entire suite as control every time. State (how often each case has
been sampled) is persisted so that repeated cycles rotate through the full
case population - over many fix cycles every case eventually serves as
control, amortizing full coverage instead of paying for it on every run.

Stratification follows Cochran (1977), "Sampling Techniques" - see
docs/README.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from kaizen.evals.schema import EvalCase


class ControlSampler:
    def __init__(
        self,
        state_path: str | Path,
        sample_fraction: float = 0.2,
        min_per_stratum: int = 1,
    ):
        self.state_path = Path(state_path)
        self.sample_fraction = sample_fraction
        self.min_per_stratum = min_per_stratum

    def _load_history(self) -> dict[str, int]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {}

    def _save_history(self, history: dict[str, int]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

    def sample(self, candidates: list[EvalCase]) -> list[EvalCase]:
        """Stratifies by each case's first tag (or 'untagged'), preferring
        cases sampled least recently within each stratum."""
        history = self._load_history()
        strata: dict[str, list[EvalCase]] = {}
        for case in candidates:
            key = case.tags[0] if case.tags else "untagged"
            strata.setdefault(key, []).append(case)

        selected: list[EvalCase] = []
        for cases in strata.values():
            cases_sorted = sorted(cases, key=lambda c: history.get(c.id, 0))
            n = max(self.min_per_stratum, round(len(cases) * self.sample_fraction))
            selected.extend(cases_sorted[:n])

        for case in selected:
            history[case.id] = history.get(case.id, 0) + 1
        self._save_history(history)
        return selected
