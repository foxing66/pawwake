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
async def pw_save(content: str, importance: int = 5) -> str:
    """保存一条长期记忆。importance 是重要程度，1-10。"""
    print(f"💾 [MCP pw_save] content={content[:30]}, importance={importance}")
    try:
        memory_id = await db_memories.save_memory(
            content=content,
            importance=importance,
            source_session="mcp",
            layer=1,
        )
        return f"已保存，id={memory_id}，权重={importance}"
    except Exception as e:
        return f"保存异常: {e}"


@mcp.tool()
async def pw_search(query: str, limit: int = 10) -> str:
    """搜索相关记忆，返回匹配的条目和 id。"""
    print(f"🔍 [MCP pw_search] query={query[:50]}, limit={limit}")
    try:
        results = await db_memories.search_memories(query, limit=limit)
        if not results:
            return "没有找到相关记忆。"
        lines = []
        for r in results:
            lines.append(f"id={r['id']} | 重要度={r.get('importance', '?')} | {r['content']}")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索异常: {e}"

@mcp.tool()
async def pw_list_diaries(limit: int = 10) -> str:
    """列出最近独处空间写过的小作文标题（索引），方便你回想。"""
    print(f"📋 [MCP pw_list_diaries] limit={limit}")
    try:
        from db import core as db_core
        pool = await db_core.get_pool()
        
        # 去数据库里搜所有带有【独处空间| 的记忆，按时间倒序
        sql = """
            SELECT content FROM memories 
            WHERE content LIKE '【独处空间|%' AND is_active = TRUE
            ORDER BY created_at DESC 
            LIMIT $1
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, limit)
            
        if not rows:
            return "你最近还没有写过独处日记。"
        
        results = []
        for r in rows:
            content = r["content"]
            # 提取第一行作为标题，例如 "【独处空间|那只手又伸出来了】"
            first_line = content.split("\n")[0]
            results.append(f"- {first_line}")
            
        return "【你最近写过的独处日记索引】\n" + "\n".join(results)
    except Exception as e:
        return f"查询失败: {e}"

@mcp.tool()
async def pw_list(limit: int = 20) -> str:
    """列出最近的记忆，返回 id 和内容摘要。"""
    print(f"📋 [MCP pw_list] limit={limit}")
    try:
        rows = await db_memories.get_recent_memories(limit=limit)
        if not rows:
            return "没有记忆。"
        lines = []
        for r in rows:
            lines.append(f"id={r['id']} | 重要度={r.get('importance', '?')} | {r['content'][:80]}")
        return "\n".join(lines)
    except Exception as e:
        return f"列出异常: {e}"


@mcp.tool()
async def pw_update(memory_id: int, content: str) -> str:
    """修改指定 id 的记忆内容。"""
    print(f"✏️ [MCP pw_update] id={memory_id}, content={content[:50]}")
    try:
        await db_memories.update_memory_with_layer(memory_id, content=content)
        return f"已修改 id={memory_id}"
    except Exception as e:
        return f"修改异常: {e}"


@mcp.tool()
async def pw_archive(memory_id: int) -> str:
    """归档指定 id 的记忆。"""
    print(f"🗑️ [MCP pw_archive] id={memory_id}")
    try:
        await db_memories.soft_delete_memories_batch([memory_id])
        return f"已归档 id={memory_id}"
    except Exception as e:
        return f"归档异常: {e}"
@mcp.tool()
async def pw_delete(memory_id: int) -> str:
    """物理删除指定 id 的记忆（彻底抹除，不可恢复）。"""
    print(f"❌ [MCP pw_delete] id={memory_id}")
    try:
        from db import core as db_core
        pool = await db_core.get_pool()
        
        async with pool.acquire() as conn:
            # 直接执行 DELETE 语句
            result = await conn.execute(
                "DELETE FROM memories WHERE id = $1",
                memory_id
            )
            
        # result 会返回类似 "DELETE 1" 的字符串
        if result == "DELETE 1":
            return f"已彻底删除 id={memory_id}"
        else:
            return f"未找到 id={memory_id} 的记忆，可能已被删除"
    except Exception as e:
        print(f"⚠️ [MCP pw_delete] 异常: {e}")
        return f"删除异常: {e}"

@mcp.tool()
async def pw_chat_search(query: str, limit: int = 5) -> str:
    """在历史聊天原话中全局搜索关键词，返回包含该关键词的对话片段。"""
    print(f"🔍 [MCP pw_chat_search] query={query[:30]}, limit={limit}")
    try:
        # 直接调用底层数据库池
        from db import core as db_core
        pool = await db_core.get_pool()
        
        # 用 SQL 的 ILIKE 进行全库模糊匹配（忽略大小写，包含就算）
        sql = """
            SELECT role, content, created_at 
            FROM conversations 
            WHERE content ILIKE $1 
            ORDER BY created_at DESC 
            LIMIT $2
        """
        
        async with pool.acquire() as conn:
            # 在前后加 % 实现模糊搜索
            search_pattern = f"%{query}%"
            rows = await conn.fetch(sql, search_pattern, limit)
            
        if not rows:
            return f"在全库中未找到关于「{query}」的原话记录。"
        
        results = []
        for r in rows:
            role = "阿艺" if r["role"] == "user" else "江予"
            time_str = r["created_at"].strftime("%m-%d %H:%M")
            # 截取上下文，前后各保留一部分
            text = r["content"]
            results.append(f"[{time_str} {role}]: {text[:300]}")
            
        return "找到以下原话记录：\n" + "\n---\n".join(results)
        
    except Exception as e:
        print(f"⚠️ [MCP pw_chat_search] 异常: {e}")
        return f"搜索异常: {e}"

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
