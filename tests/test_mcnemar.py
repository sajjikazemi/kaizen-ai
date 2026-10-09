from kaizen.evaluate.mcnemar import build_contingency_table, mcnemar_test


def test_contingency_table_counts():
    baseline = {"a": True, "b": False, "c": True, "d": False}
    candidate = {"a": True, "b": True, "c": False, "d": False}
    table = build_contingency_table(baseline, candidate, ["a", "b", "c", "d"])
    assert table.both_pass == 1  # a
    assert table.fixed == 1       # b: fail -> pass
    assert table.regressed == 1   # c: pass -> fail
    assert table.both_fail == 1   # d
    assert table.n == 4
    assert table.baseline_correct == 2  # a, c
    assert table.candidate_correct == 2  # a, b


def test_mcnemar_flat_when_no_discordant_pairs():
    baseline = {"a": True, "b": False}
    candidate = {"a": True, "b": False}
    table = build_contingency_table(baseline, candidate, ["a", "b"])
    result = mcnemar_test(table)
    assert result.p_value == 1.0
    assert result.direction == "flat"


def test_mcnemar_detects_gain():
    # 10 fixed, 0 regressed: should be a significant gain.
    baseline = {f"t{i}": False for i in range(10)}
    candidate = {f"t{i}": True for i in range(10)}
    ids = list(baseline)
    table = build_contingency_table(baseline, candidate, ids)
    result = mcnemar_test(table)
    assert result.direction == "gain"
    assert result.p_value < 0.05


def test_mcnemar_detects_loss():
    baseline = {f"c{i}": True for i in range(10)}
    candidate = {f"c{i}": False for i in range(10)}
    ids = list(baseline)
    table = build_contingency_table(baseline, candidate, ids)
    result = mcnemar_test(table)
    assert result.direction == "loss"
    assert result.p_value < 0.05


def test_mcnemar_flat_when_roughly_balanced_noise():
    # 2 fixed, 2 regressed out of 50 -> should NOT be significant (noise).
    baseline = {f"n{i}": True for i in range(50)}
    candidate = dict(baseline)
    candidate["n0"] = False
    candidate["n1"] = False
    baseline["n2"] = False
    baseline["n3"] = False
    candidate["n2"] = True
    candidate["n3"] = True
    ids = list(baseline)
    table = build_contingency_table(baseline, candidate, ids)
    result = mcnemar_test(table)
    assert result.direction == "flat"
