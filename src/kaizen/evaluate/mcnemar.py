"""Paired binary comparison (McNemar's test) for baseline vs. candidate.

Baseline and candidate answer the SAME eval cases, so this is a paired
design: McNemar's test (not a plain accuracy-diff or independent-sample
test) is the statistically correct tool, and its exact form is valid even
at the small sample sizes a treatment/control split typically has.

References: McNemar (1947); Dietterich (1998); Dror et al. (2018) - see
docs/README.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContingencyTable:
    both_pass: int      # baseline pass, candidate pass
    fixed: int           # baseline fail -> candidate pass
    regressed: int       # baseline pass -> candidate fail
    both_fail: int        # baseline fail, candidate fail

    @property
    def n(self) -> int:
        return self.both_pass + self.fixed + self.regressed + self.both_fail

    @property
    def baseline_correct(self) -> int:
        return self.both_pass + self.regressed

    @property
    def candidate_correct(self) -> int:
        return self.both_pass + self.fixed


@dataclass
class McNemarResult:
    table: ContingencyTable
    p_value: float
    direction: str  # "gain" | "loss" | "flat"


def build_contingency_table(
    baseline: dict[str, bool], candidate: dict[str, bool], case_ids: list[str]
) -> ContingencyTable:
    both_pass = fixed = regressed = both_fail = 0
    for cid in case_ids:
        b = baseline.get(cid, False)
        c = candidate.get(cid, False)
        if b and c:
            both_pass += 1
        elif not b and c:
            fixed += 1
        elif b and not c:
            regressed += 1
        else:
            both_fail += 1
    return ContingencyTable(both_pass, fixed, regressed, both_fail)


def mcnemar_test(table: ContingencyTable, alpha: float = 0.05) -> McNemarResult:
    """Exact two-sided McNemar's test on the discordant pairs.

    Only `fixed` (baseline-fail -> candidate-pass) and `regressed`
    (baseline-pass -> candidate-fail) carry information; concordant pairs
    are ignored, exactly as the test requires.
    """
    from scipy.stats import binomtest

    discordant = table.fixed + table.regressed
    if discordant == 0:  # noqa: SIM108 - ternary form here reads worse, not better
        p_value = 1.0
    else:
        p_value = binomtest(table.fixed, discordant, p=0.5, alternative="two-sided").pvalue

    if p_value >= alpha:
        direction = "flat"
    elif table.fixed > table.regressed:
        direction = "gain"
    else:
        direction = "loss"

    return McNemarResult(table=table, p_value=p_value, direction=direction)
