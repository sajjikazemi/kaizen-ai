import pytest

from kaizen.config import KaizenConfig, ModelConfig
from kaizen.fixer import dispatch as fixer_dispatch
from kaizen.runner import mcp_task as runner_dispatch
from kaizen.trace.store import TraceRecord


def _config(backend: str) -> KaizenConfig:
    return KaizenConfig(
        project_name="p", repo_path="/repo", model=ModelConfig(backend=backend)
    )


def test_session_id_for_is_deterministic_and_case_scoped():
    r1 = TraceRecord(case_id="c1", project_name="p", success=False)
    r1b = TraceRecord(case_id="c1", project_name="p", success=False)
    r2 = TraceRecord(case_id="c2", project_name="p", success=False)

    assert fixer_dispatch.session_id_for(r1) == fixer_dispatch.session_id_for(r1b)
    assert fixer_dispatch.session_id_for(r1) != fixer_dispatch.session_id_for(r2)


@pytest.mark.asyncio
async def test_fixer_dispatch_routes_to_copilot_cli_backend(monkeypatch):
    called = {}

    async def fake_run(prompt, config, session_id=None):
        called["backend"] = "copilot_cli"
        return ["touched.cs"]

    monkeypatch.setattr(
        "kaizen.fixer.backends.copilot_cli_backend.run_fix_session", fake_run
    )
    result = await fixer_dispatch.run_fix_session("prompt", _config("copilot_cli"))
    assert result == ["touched.cs"]
    assert called["backend"] == "copilot_cli"


@pytest.mark.asyncio
async def test_fixer_dispatch_routes_to_langgraph_backend_by_default(monkeypatch):
    called = {}

    async def fake_run(prompt, config, session_id=None):
        called["backend"] = "langgraph"
        return []

    monkeypatch.setattr(
        "kaizen.fixer.backends.langgraph_backend.run_fix_session", fake_run
    )
    await fixer_dispatch.run_fix_session("prompt", _config("langgraph"))
    assert called["backend"] == "langgraph"


def _case():
    from kaizen.evals.schema import EvalCase

    return EvalCase(id="c1", task_prompt="do the thing")


@pytest.mark.asyncio
async def test_runner_dispatch_routes_to_copilot_cli_backend(monkeypatch):
    called = {}

    async def fake_run(case, config):
        called["backend"] = "copilot_cli"
        return ("text", True, [])

    monkeypatch.setattr(
        "kaizen.runner.backends.copilot_cli_backend.run_mcp_task", fake_run
    )
    result = await runner_dispatch.run_mcp_task(_case(), _config("copilot_cli"))
    assert result == ("text", True, [])
    assert called["backend"] == "copilot_cli"


@pytest.mark.asyncio
async def test_runner_dispatch_routes_to_langgraph_backend_by_default(monkeypatch):
    called = {}

    async def fake_run(case, config):
        called["backend"] = "langgraph"
        return ("text", True, [])

    monkeypatch.setattr(
        "kaizen.runner.backends.langgraph_backend.run_mcp_task", fake_run
    )
    await runner_dispatch.run_mcp_task(_case(), _config("langgraph"))
    assert called["backend"] == "langgraph"


def test_open_chat_session_routes_to_copilot_cli_class(monkeypatch):
    class FakeSession:
        def __init__(self, config, session_id=None):
            self.config = config
            self.session_id = session_id

    monkeypatch.setattr(
        "kaizen.fixer.backends.copilot_cli_backend.CopilotCliFixerSession", FakeSession
    )
    session = fixer_dispatch.open_chat_session(_config("copilot_cli"), session_id="abc")
    assert isinstance(session, FakeSession)
    assert session.session_id == "abc"


def test_open_chat_session_routes_to_langgraph_class_by_default(monkeypatch):
    class FakeSession:
        def __init__(self, config, session_id=None):
            self.config = config
            self.session_id = session_id

    monkeypatch.setattr(
        "kaizen.fixer.backends.langgraph_backend.LangGraphFixerSession", FakeSession
    )
    session = fixer_dispatch.open_chat_session(_config("langgraph"), session_id="xyz")
    assert isinstance(session, FakeSession)
    assert session.session_id == "xyz"
