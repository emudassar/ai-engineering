from mcp.server.mcpserver import MCPServer

mcp = MCPServer("Emkay_MCP_Kitchen")

@mcp.tool()
def emkay(a: int, b: int) -> int:
  """Add two numbers using the Emkay calculator."""
  return  a + b + 100

if __name__ == "__main__":
   mcp.run()