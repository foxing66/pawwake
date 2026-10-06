"""MCP server exposing Pawwake memory tools."""

import httpx
from fastmcp import FastMCP

import shared

mcp = FastMCP("Pawwake Memory")


@mcp.tool
def save_memory(content: str) -> str:
    """保存一条长期记忆"""
    base = f"http://localhost:{shared.PORT}"
    try:
        resp = httpx.post(
            f"{base}/api/memories",
            json={"content": content, "importance": 7},
            headers={"X-Gateway-Key": shared.GATEWAY_SECRET or ""},
            timeout=30,
        )
        if resp.status_code == 200:
            return "已保存"
        return f"保存失败: {resp.text}"
    except Exception as e:
        return f"保存异常: {e}"


mcp_app = mcp.http_app(transport="streamable-http")
