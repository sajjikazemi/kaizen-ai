"""Runs the Fixer's actual Claude session with Tier-3 paths locked out."""
from __future__ import annotations

from kaizen.fixer.tiering import classify_tier
from kaizen.config import PatchTier


async def run_fix_session(prompt: str, repo_path: str) -> list[str]:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    touched_files: list[str] = []

    async def can_use_tool(tool_name, tool_input, _context):
        if tool_name in ("Write", "Edit"):
            path = tool_input.get("file_path", "")
            if classify_tier(path) == PatchTier.TIER_3_LOCKED:
                return {
                    "behavior": "deny",
                    "message": f"{path} is a locked (Tier 3) path; Fixer may not modify it.",
                }
            touched_files.append(path)
        return {"behavior": "allow", "updatedInput": tool_input}

    options = ClaudeAgentOptions(
        cwd=repo_path,
        allowed_tools=["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
        permission_mode="default",
        can_use_tool=can_use_tool,
        max_turns=20,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for _message in client.receive_response():
            pass

    return touched_files
