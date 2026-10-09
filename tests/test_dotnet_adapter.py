from kaizen.adapters.base import CommandResult
from kaizen.adapters.dotnet import DotnetAdapter


def test_parses_build_error():
    adapter = DotnetAdapter.__new__(DotnetAdapter)  # skip __init__, no subprocess needed
    result = CommandResult(
        command=["dotnet", "build"],
        exit_code=1,
        stdout="Program.cs(12,5): error CS0103: The name 'foo' does not exist [MyProj.csproj]\n",
        stderr="",
    )
    errors = adapter.parse_errors(result)
    assert len(errors) == 1
    assert errors[0].file == "Program.cs"
    assert errors[0].line == 12
    assert errors[0].code == "CS0103"


def test_parses_test_failure():
    adapter = DotnetAdapter.__new__(DotnetAdapter)
    result = CommandResult(
        command=["dotnet", "test"],
        exit_code=1,
        stdout="Failed MyNamespace.MyTests.MyTest_ShouldDoThing [12 ms]\n",
        stderr="",
    )
    errors = adapter.parse_errors(result)
    assert len(errors) == 1
    assert errors[0].code == "MyNamespace.MyTests.MyTest_ShouldDoThing"


def test_falls_back_when_unparseable():
    adapter = DotnetAdapter.__new__(DotnetAdapter)
    result = CommandResult(command=["x"], exit_code=1, stdout="boom", stderr="")
    errors = adapter.parse_errors(result)
    assert len(errors) == 1
