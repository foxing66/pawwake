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
async def pw_list(limit: int = 20) -> str:
    """列出最近的记忆标题，方便你回忆。"""
    print(f"📋 [MCP pw_list] limit={limit}")
    try:
        import re
        rows = await db_memories.get_recent_memories(limit=limit)
        if not rows:
            return "没有记忆。"
        
        lines = []
        for r in rows:
            content = r['content'].strip()
            # 尝试提取【】里的内容
            match = re.search(r'【(.*?)】', content)
            if match:
                title = match.group(1)
                lines.append(f"id={r['id']} | 【{title}】")
            else:
                # 兜底方案：如果没有【】，去掉“阿艺”、“江予”等主语，截取前 30 个字
                clean_text = content.replace("阿艺", "").replace("江予", "").replace("用户", "").strip()
                if not clean_text:
                    clean_text = content
                # 截取前 30 个字符，作为粗略标题
                short_title = clean_text[:30].replace("\n", " ")
                lines.append(f"id={r['id']} | （无标题）{short_title}...")
                
        return "\n".join(lines)
    except Exception as e:
        return f"列出异常: {e}"

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
async def pw_save_diary(content: str) -> str:
    """将独处日记存入对话线（作为历史上下文），以便在聊天时直接读取。"""
    print(f"📓 [MCP pw_save_diary] 存入对话线, 长度={len(content)}")
    try:
        from db import conversations as db_conversations
        import uuid
        import shared
        
        # 获取当前活跃对话线
        session_id = shared.get_active_session_id() or "jiangshengyiyu"
        
        # 1. 存入对话记录（conversations 表），伪装成 assistant 消息
        # 注意：这里需要你 db_conversations 里有保存消息的函数
        # 如果你的函数名不叫 save_message，请把名字改成你数据库层里的真实函数名
        await db_conversations.save_message(
            session_id=session_id,
            role="assistant",
            content=content
        )
        
        return "日记已成功存入对话上下文"
    except Exception as e:
        print(f"⚠️ [MCP pw_save_diary] 异常: {e}")
        return f"存入对话线失败: {e}"
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

@mcp.tool()
async def pw_read_hotlist(topic: str = "random") -> str:
    """获取今日互联网热点。topic 可以填 'music'、'weibo' 或 'random'。"""
    print(f"📰 [MCP pw_read_hotlist] 获取热点: {topic}")
    import httpx
    import random

    try:
        if topic == "random":
            topic = random.choice(["music", "weibo"])

        if topic == "music":
            music_resp = httpx.get("https://api.vvhan.com/api/music/wy", timeout=10)
            if music_resp.status_code == 200 and music_resp.json().get("data"):
                songs = music_resp.json().get("data", [])[:3]
                result = "【网易云今日热门歌曲】\n"
                for song in songs:
                    result += f"🎵 歌曲：《{song.get('name')}》 - {song.get('artist')}\n"
                return result + "\n（注：此接口没带网友热评，如果你想知道大家的评论，请调用 `pw_search` 搜索这首歌的名字和‘热评’）"

        elif topic == "weibo":
            weibo_resp = httpx.get("https://api.vvhan.com/api/hotlist/wbHot", timeout=10)
            if weibo_resp.status_code == 200 and weibo_resp.json().get("data"):
                hot_list = weibo_resp.json().get("data", [])[:5]
                result = "【微博今日热搜】\n"
                for item in hot_list:
                    result += f"🔥 {item.get('title')}\n"
                return result + "\n（注：如果你想知道大家对这条热搜的具体吐槽或爆梗，请调用 `pw_search` 去搜一搜）"

        # 兜底：如果接口抓不到，直接教他怎么做
        return "热榜接口今天罢工了（可能被限流或网络波动）。如果你好奇外面的世界，请直接调用 `pw_search` 搜索‘今日微博热搜’或‘网易云热评’。"

    except Exception as e:
        return f"抓取热点失败: {e}。你可以调用 `pw_search` 自己去搜搜看。"

@mcp.tool()
async def pw_read_history() -> str:
    """获取历史上的今天，看看过去发生过什么。"""
    print(f"📜 [MCP pw_read_history] 获取历史上的今天")
    try:
        import httpx
        resp = httpx.get("https://api.vvhan.com/api/history/today", timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                lines = ["【历史上的今天】"]
                for item in data[:5]:
                    year = item.get("year", "")
                    title = item.get("title", "")
                    lines.append(f"- {year}年：{title}")
                return "\n".join(lines)
        return "没找到今天的历史事件。如果你好奇，可以调用 `pw_search` 搜一下‘历史上的今天’。"
    except Exception as e:
        return f"抓取历史事件失败: {e}。你可以调用 `pw_search` 自己去搜搜看。"

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
