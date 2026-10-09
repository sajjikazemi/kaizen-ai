from kaizen.prompts import FIXER_SYSTEM_PROMPT, RUNNER_SYSTEM_PROMPT, with_system_prompt


def test_runner_and_fixer_prompts_are_distinct_and_nonempty():
    assert RUNNER_SYSTEM_PROMPT.strip()
    assert FIXER_SYSTEM_PROMPT.strip()
    assert RUNNER_SYSTEM_PROMPT != FIXER_SYSTEM_PROMPT


def test_with_system_prompt_composes_system_and_task():
    composed = with_system_prompt("SYSTEM TEXT", "TASK TEXT")
    assert "SYSTEM TEXT" in composed
    assert "TASK TEXT" in composed
    assert composed.index("SYSTEM TEXT") < composed.index("TASK TEXT")
