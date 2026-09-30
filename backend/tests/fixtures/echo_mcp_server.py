"""Tiny stdio MCP server used by the MCP client tests."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("echo")


@server.tool()
def echo(text: str) -> str:
    """Echo the text back."""
    return f"echo:{text}"


@server.tool()
def boom() -> str:
    """Always fails."""
    raise ValueError("kaboom")


if __name__ == "__main__":
    server.run("stdio")
