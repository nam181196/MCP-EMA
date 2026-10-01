import asyncio
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("test")
app = mcp.sse_app(sse_path="/sse", message_path="/messages")
print([route.path for route in app.routes])
