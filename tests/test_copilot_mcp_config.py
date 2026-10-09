from kaizen.config import KaizenConfig, McpServerConfig
from kaizen.copilot_cli.mcp_config import build_mcp_config


def _config(**mcp_kwargs) -> KaizenConfig:
    return KaizenConfig(
        project_name="p",
        repo_path="/repo",
        mcp_server=McpServerConfig(**mcp_kwargs) if mcp_kwargs else None,
    )


def test_build_mcp_config_returns_none_without_mcp_server():
    assert build_mcp_config(_config()) is None


def test_build_mcp_config_matches_copilot_schema():
    config = _config(command="dotnet", args=["run"], cwd="/repo/src", env={"FOO": "bar"})
    result = build_mcp_config(config)
    assert result == {
        "mcpServers": {
            "target": {
                "type": "local",
                "command": "dotnet",
                "args": ["run"],
                "env": {"FOO": "bar"},
                "tools": ["*"],
                "cwd": "/repo/src",
            }
        }
    }


def test_build_mcp_config_omits_cwd_when_unset():
    config = _config(command="dotnet", args=["run"])
    result = build_mcp_config(config)
    assert "cwd" not in result["mcpServers"]["target"]
