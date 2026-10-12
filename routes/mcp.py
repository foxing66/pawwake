"""MCP server exposing Pawwake memory tools."""

import httpx
import os
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import shared
from db import memories as db_memories

mcp = FastMCP("Pawwake Memory")


@mcp.tool()
async def save_memory(content: str) -> str:
    """保存一条长期记忆"""
    print(f"💾 [MCP save_memory] 被调用，content={content[:50]}")
    try:
        memory_id = await db_memories.save_memory(
            content=content,
            importance=7,
            source_session="mcp",
            layer=1,
        )
        print(f"💾 [MCP save_memory] 保存成功，id={memory_id}")
        return "已保存"
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
