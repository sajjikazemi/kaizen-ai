"""Entry points for `langgraph dev` / LangGraph Studio.

Exposes the Fixer agent's graph so you can watch an in-flight fix - including
Tier-2 human-approval interrupts - and approve/reject it visually in Studio,
as an alternative to the CLI's console y/n prompt (`fixer_graph.run_fix_session`
uses the same graph builder, so behavior is identical either way).

Point the `KAIZEN_CONFIG` env var at a target project's `kaizen.yaml`; falls
back to the bundled example project if unset.
"""
from __future__ import annotations

import os

from kaizen.azure_model import resolve_model
from kaizen.config import KaizenConfig
from kaizen.fixer.backends.langgraph_backend import build_fixer_agent

_THIS_DIR = os.path.dirname(__file__)
_DEFAULT_CONFIG = os.path.join(
    _THIS_DIR, "..", "..", "examples", "sample_dotnet_project", "kaizen.yaml"
)
_CONFIG_PATH = os.environ.get("KAIZEN_CONFIG", _DEFAULT_CONFIG)
_config = KaizenConfig.load(_CONFIG_PATH)

# Studio only needs something to visualize/step through; the CLI's real `fix`
# command builds its own graph (with its own touched_files list) per run.
_touched_files_sink: list[str] = []

fixer_graph = build_fixer_agent(
    resolve_model(_config.model, "fixer"), _config.repo_path, _touched_files_sink
)
