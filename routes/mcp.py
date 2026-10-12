"""MCP server exposing Pawwake memory tools."""

import httpx
import os
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import shared

mcp = FastMCP("Pawwake Memory")


@mcp.tool()
def save_memory(content: str) -> str:
    """保存一条长期记忆"""
    base = f"http://localhost:{shared.PORT}"
    print(f"💾 [MCP save_memory] 被调用，content={content[:50]}")
    print(f"💾 [MCP save_memory] 请求 URL: {base}/api/memories")
    try:
        resp = httpx.post(
            f"{base}/api/memories",
            json={"content": content, "importance": 7},
            headers={"X-Gateway-Key": shared.GATEWAY_SECRET or ""},
            timeout=30,
        )
        print(f"💾 [MCP save_memory] 响应 status={resp.status_code}, body={resp.text[:200]}")
        if resp.status_code == 200:
            return "已保存"
        return f"保存失败: {resp.text}"
    except Exception as e:
        print(f"⚠️ [MCP save_memory] 异常: {e}")
        return f"保存异常: {e}"


mcp_app = mcp.http_app(path="/")

# ---------- MCP token 校验 ----------
MCP_TOKEN = os.environ.get("MCP_TOKEN", "")


class MCPTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if MCP_TOKEN:
            token = request.headers.get("X-MCP-Token", "")
            if token != MCP_TOKEN:
                return JSONResponse(
                    status_code=401,
                    content={"error": "invalid mcp token"},
                )
        return await call_next(request)


mcp_app.add_middleware(MCPTokenMiddleware)
# ---------- token 校验结束 ----------
