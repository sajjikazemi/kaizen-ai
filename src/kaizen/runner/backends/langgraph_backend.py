"""Executes one task_prompt eval case against the target's MCP server.

Provider-agnostic: `config.model.runner_model` is a ``"provider:model"``
string (or `config.model.azure.runner_deployment` for Azure OpenAI), so the
Runner (which typically only needs to drive tool calls, not reason deeply)
can use a cheap/fast model independent of the Fixer's model.
"""
from __future__ import annotations

from kaizen.azure_model import resolve_model
from kaizen.config import KaizenConfig
from kaizen.evals.schema import EvalCase
from kaizen.prompts import RUNNER_SYSTEM_PROMPT


async def run_mcp_task(case: EvalCase, config: KaizenConfig) -> tuple[str, bool, list[str]]:
    """Runs ``case.task_prompt`` through a LangGraph agent connected to the
    target's MCP server.

    Returns (full_text_output, success, raw_tool_errors).
    """
    from langchain.agents import create_agent
    from langchain_mcp_adapters.client import MultiServerMCPClient

    if config.mcp_server is None:
        raise ValueError(
            f"Eval case {case.id!r} uses task_prompt but no mcp_server is configured "
            f"in kaizen.yaml for project {config.project_name!r}"
        )

    client = MultiServerMCPClient(
        {
            "target": {
                "command": config.mcp_server.command,
                "args": config.mcp_server.args,
                "env": config.mcp_server.env,
                "transport": "stdio",
            }
        }
    )
    tools = await client.get_tools()
    agent = create_agent(resolve_model(config.model, "runner"), tools, system_prompt=RUNNER_SYSTEM_PROMPT)

    tool_errors: list[str] = []
    result = await agent.ainvoke({"messages": [{"role": "user", "content": case.task_prompt}]})

    messages = result.get("messages", [])
    text_chunks = [m.content for m in messages if getattr(m, "type", None) == "ai" and isinstance(m.content, str)]
    for m in messages:
        if getattr(m, "type", None) == "tool" and getattr(m, "status", None) == "error":
            tool_errors.append(str(m.content))

    full_text = "\n".join(text_chunks)
    success = not tool_errors
    if case.expect_output_contains:
        success = success and all(needle in full_text for needle in case.expect_output_contains)
    return full_text, success, tool_errors

