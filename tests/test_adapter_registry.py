import pytest

from kaizen.adapters import get_adapter
from kaizen.adapters.dotnet import DotnetAdapter
from kaizen.adapters.pytest_adapter import PytestAdapter
from kaizen.config import AdapterConfig, KaizenConfig


def _config(adapter_name: str) -> KaizenConfig:
    return KaizenConfig(
        project_name="p", repo_path="/repo", adapter=AdapterConfig(name=adapter_name)
    )


def test_dispatches_dotnet():
    assert isinstance(get_adapter(_config("dotnet")), DotnetAdapter)


def test_dispatches_pytest():
    assert isinstance(get_adapter(_config("pytest")), PytestAdapter)


def test_unknown_adapter_raises():
    with pytest.raises(ValueError, match="Unknown adapter"):
        get_adapter(_config("rustc"))
