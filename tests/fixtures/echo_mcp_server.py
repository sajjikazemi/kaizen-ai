"""A minimal real MCP server, run as a subprocess over stdio by
test_mcp_client.py - not mocked, so the test exercises the actual
protocol round-trip."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("echo-test-server")


@mcp.tool()
def echo(text: str) -> str:
    return text


@mcp.tool()
def boom(message: str) -> str:
    raise ValueError(message)


if __name__ == "__main__":
    mcp.run(transport="stdio")
