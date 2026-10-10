from kaizen.adapters.base import CommandResult
from kaizen.adapters.pytest_adapter import PytestAdapter


def test_parses_test_failure():
    adapter = PytestAdapter.__new__(PytestAdapter)  # skip __init__, no subprocess needed
    result = CommandResult(
        command=["pytest"],
        exit_code=1,
        stdout=(
            "FAILED test_calculator.py::test_add - assert -1 == 5\n"
            "1 failed, 2 passed in 0.03s\n"
        ),
        stderr="",
    )
    errors = adapter.parse_errors(result)
    assert len(errors) == 1
    assert errors[0].file == "test_calculator.py"
    assert errors[0].code == "test_calculator.py::test_add"
    assert errors[0].message == "assert -1 == 5"


def test_parses_collection_error():
    adapter = PytestAdapter.__new__(PytestAdapter)
    result = CommandResult(
        command=["pytest"],
        exit_code=2,
        stdout="ERROR test_calculator.py - ModuleNotFoundError: no module named 'foo'\n",
        stderr="",
    )
    errors = adapter.parse_errors(result)
    assert len(errors) == 1
    assert errors[0].file == "test_calculator.py"
    assert "ModuleNotFoundError" in errors[0].message


def test_falls_back_when_unparseable():
    adapter = PytestAdapter.__new__(PytestAdapter)
    result = CommandResult(command=["pytest"], exit_code=1, stdout="boom", stderr="")
    errors = adapter.parse_errors(result)
    assert len(errors) == 1
