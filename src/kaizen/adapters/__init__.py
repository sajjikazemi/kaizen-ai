"""Adapter registry: maps `adapter.name` in kaizen.yaml to a ProjectAdapter."""
from __future__ import annotations

from kaizen.adapters.base import ProjectAdapter
from kaizen.adapters.dotnet import DotnetAdapter
from kaizen.adapters.pytest_adapter import PytestAdapter
from kaizen.config import KaizenConfig

_ADAPTERS: dict[str, type[ProjectAdapter]] = {
    "dotnet": DotnetAdapter,
    "pytest": PytestAdapter,
}


def get_adapter(config: KaizenConfig) -> ProjectAdapter:
    """Instantiate the ``ProjectAdapter`` named by ``config.adapter.name``."""
    try:
        adapter_cls = _ADAPTERS[config.adapter.name]
    except KeyError:
        raise ValueError(
            f"Unknown adapter {config.adapter.name!r}. Available: {sorted(_ADAPTERS)}"
        ) from None
    return adapter_cls(config.repo_path)
