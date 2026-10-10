"""A tiny, deliberately-buggy module for the quickstart example.

`subtract` has an off-by-one-operator bug - it adds instead of subtracting.
`kaizen run` catches this via the failing test in test_calculator.py, and
`kaizen fix` proposes the one-line patch.
"""


def add(a: int, b: int) -> int:
    return a + b


def subtract(a: int, b: int) -> int:
    return a + b  # bug: should be `a - b`
