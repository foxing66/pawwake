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
@mcp.tool()
async def memory_search(query: str, limit: int = 10) -> str:
    """搜索相关记忆，返回匹配的条目和 id。"""
    print(f"🔍 [MCP memory_search] query={query[:50]}, limit={limit}")
    try:
        results = await db_memories.search_memories(query, limit=limit)
        if not results:
            return "没有找到相关记忆。"
        lines = []
        for r in results:
            lines.append(f"id={r['id']} | 重要度={r.get('importance', '?')} | {r['content']}")
        return "\n".join(lines)
    except Exception as e:
        print(f"⚠️ [MCP memory_search] 异常: {e}")
        return f"搜索异常: {e}"
@mcp.tool()
async def memory_update(memory_id: int, content: str) -> str:
    """修改指定 id 的记忆内容。"""
    print(f"✏️ [MCP memory_update] id={memory_id}, content={content[:50]}")
    try:
        await db_memories.update_memory_with_layer(memory_id, content=content)
        print(f"✏️ [MCP memory_update] 修改成功，id={memory_id}")
        return f"已修改 id={memory_id}"
    except Exception as e:
        print(f"⚠️ [MCP memory_update] 异常: {e}")
        return f"修改异常: {e}"


@mcp.tool()
async def memory_delete(memory_id: int) -> str:
    """归档指定 id 的记忆。"""
    print(f"🗑️ [MCP memory_delete] id={memory_id}")
    try:
        await db_memories.soft_delete_memories_batch([memory_id])
        print(f"🗑️ [MCP memory_delete] 归档成功，id={memory_id}")
        return f"已归档 id={memory_id}"
    except Exception as e:
        print(f"⚠️ [MCP memory_delete] 异常: {e}")
        return f"归档异常: {e}"

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
