"""Orchestrator — step-based pipeline functions for Novalist v2.

Each step function is an async generator yielding SSE-encoded bytes.
Agents run in dedicated threads; a thread-safe queue bridges to async.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
import logging
import threading
from typing import AsyncIterator
from queue import Queue, Empty

from strands import Agent
from strands.multiagent import GraphBuilder

from app.agents.models import get_planning_model, get_creative_model, get_model
from app.agents.hooks import MaxTokensContinuationHook
from app.models.novel_store import NovelStore
from app.models.memory import MemoryManager
from app.models.schemas import (
    Step1Request,
    Step2Request,
    Step3ChapterRequest,
    ChatRequest,
)

# Import system prompts from agent modules
from app.agents.story_architect import SYSTEM_PROMPT as ARCH_PROMPT
from app.agents.character_dev import SYSTEM_PROMPT as CHAR_PROMPT
from app.agents.world_builder import SYSTEM_PROMPT as WORLD_PROMPT
from app.agents.plot_weaver import SYSTEM_PROMPT as PLOT_PROMPT
from app.agents.prose_writer import SYSTEM_PROMPT as PROSE_PROMPT
from app.agents.editor import SYSTEM_PROMPT as EDITOR_PROMPT

logger = logging.getLogger(__name__)

# ── Constants & helpers ──────────────────────────────────────────────

AGENT_NAMES_CN = {
    "story_architect": "故事架构师",
    "character_developer": "角色开发师",
    "world_builder": "世界构建师",
    "plot_weaver": "情节编织师",
    "prose_writer": "文笔写手",
    "editor": "编辑",
    "chat": "创意顾问",
}

_SENTINEL = None

CHAT_SYSTEM_PROMPT = """你是一位经验丰富的小说创意顾问。你帮助作者头脑风暴故事创意、讨论角色设计、探索不同的情节可能性。
你的回答应该富有启发性和创造性，帮助作者找到灵感。
用中文回答，风格亲切专业。"""


def _sse_event(event_type: str, data: dict) -> bytes:
    """Format a dict as an SSE event bytes."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n".encode("utf-8")


SSE_HEARTBEAT = b": heartbeat\n\n"


def _make_streaming_callback(agent_name: str, queue: Queue):
    """Create a callback_handler that batches text chunks before pushing to SSE queue.

    Accumulates tokens and flushes every 0.5s or 100 chars, whichever comes first.
    """
    cn_name = AGENT_NAMES_CN.get(agent_name, agent_name)
    buffer = []
    last_flush = [time.time()]

    def _flush():
        if buffer:
            text = "".join(buffer)
            buffer.clear()
            last_flush[0] = time.time()
            queue.put(_sse_event("text_chunk", {
                "agent": agent_name,
                "agent_name": cn_name,
                "content": text,
            }))

    def callback(**kwargs):
        if "data" in kwargs:
            text = kwargs["data"]
            if text:
                buffer.append(text)
                if len("".join(buffer)) >= 100 or (time.time() - last_flush[0]) >= 0.5:
                    _flush()

    return callback, _flush


# ── Streaming buffer that also accumulates full text ────────────────

def _make_streaming_callback_with_accumulator(agent_name: str, queue: Queue):
    """Like _make_streaming_callback but also accumulates full output text."""
    cn_name = AGENT_NAMES_CN.get(agent_name, agent_name)
    buffer = []
    full_text = []
    last_flush = [time.time()]

    def _flush():
        if buffer:
            text = "".join(buffer)
            buffer.clear()
            last_flush[0] = time.time()
            queue.put(_sse_event("text_chunk", {
                "agent": agent_name,
                "agent_name": cn_name,
                "content": text,
            }))

    def callback(**kwargs):
        if "data" in kwargs:
            text = kwargs["data"]
            if text:
                buffer.append(text)
                full_text.append(text)
                if len("".join(buffer)) >= 100 or (time.time() - last_flush[0]) >= 0.5:
                    _flush()

    def get_full_text() -> str:
        return "".join(full_text)

    return callback, _flush, get_full_text


# ── Async SSE consumer (shared by all step functions) ────────────────

async def _consume_queue(queue: Queue) -> AsyncIterator[bytes]:
    """Drain the queue as an async iterator, emitting heartbeats every 15s."""
    last_event_time = time.time()
    while True:
        try:
            item = queue.get_nowait()
            if item is _SENTINEL:
                break
            last_event_time = time.time()
            yield item
        except Empty:
            if time.time() - last_event_time > 15:
                last_event_time = time.time()
                yield SSE_HEARTBEAT
            await asyncio.sleep(0.1)


# ── Step 1: structure + characters + world (parallel graph) ──────────

def _build_step1_prompt(req: Step1Request) -> str:
    chars_desc = ""
    if req.characters:
        chars_desc = "\n".join(
            f"- {c.name}（{c.role}）：{c.description} | 动机：{c.motivation}"
            for c in req.characters
        )
    else:
        chars_desc = "请根据故事前提和类型创建合适的角色。"

    return f"""请按照以下规格设计小说的基础框架：

**故事前提**：{req.premise}
**类型**：{req.genre.value}
**叙事结构**：{req.structure.value}
**写作风格**：{req.style.value}
**叙事视角**：{req.pov.value}
**目标章节数**：{req.target_chapters}
**基调**：{req.tone}

**角色**：
{chars_desc}

**世界设定**：{req.setting_notes or '请根据前提确定最佳设定。'}
**主题方向**：{req.theme_notes or '请挖掘最有力的主题角度。'}

请根据你的专长完成你的职责。所有创作内容必须使用简体中文。
"""


def _run_step1_in_thread(
    prompt: str, novel_id: str, user_id: str, queue: Queue
):
    """Run story_architect + character_developer + world_builder in parallel via Graph."""
    try:
        # Load memory context and prepend to prompt
        memory_mgr = MemoryManager(user_id)
        memory_context = memory_mgr.format_context()
        if memory_context:
            prompt = memory_context + prompt

        queue.put(_sse_event("agent_start", {
            "agent": "story_architect,character_developer,world_builder",
            "content": "故事架构师、角色开发师、世界构建师 开始并行工作...",
        }))

        # Build agents with streaming callbacks that accumulate full text
        agents_config = [
            ("story_architect", ARCH_PROMPT, get_planning_model),
            ("character_developer", CHAR_PROMPT, get_planning_model),
            ("world_builder", WORLD_PROMPT, get_planning_model),
        ]

        agents = {}
        flush_fns = []
        get_text_fns = {}
        for name, prompt_text, model_fn in agents_config:
            cb, flush, get_text = _make_streaming_callback_with_accumulator(name, queue)
            flush_fns.append(flush)
            get_text_fns[name] = get_text
            agents[name] = Agent(
                name=name,
                model=model_fn(),
                system_prompt=prompt_text,
                tools=[],
                callback_handler=cb,
                hooks=[MaxTokensContinuationHook()],
            )

        # Build graph: three parallel entry points, no downstream
        builder = GraphBuilder()
        for name, agent in agents.items():
            builder.add_node(agent, name)

        builder.set_entry_point("story_architect")
        builder.set_entry_point("character_developer")
        builder.set_entry_point("world_builder")

        builder.set_execution_timeout(600)
        builder.set_node_timeout(300)

        graph = builder.build()

        result = graph(prompt)
        for fn in flush_fns:
            fn()

        # Extract outputs — prefer accumulated stream text, fall back to result
        field_map = {
            "story_architect": "structure",
            "character_developer": "characters",
            "world_builder": "world",
        }
        outputs = {}

        for node_id in ["story_architect", "character_developer", "world_builder"]:
            # First try the accumulated streamed text
            streamed = get_text_fns[node_id]()
            if streamed:
                output_text = streamed
            elif hasattr(result, "results") and result.results:
                node_result = result.results.get(node_id)
                if node_result and node_result.result:
                    output_text = str(node_result.result)
                else:
                    output_text = ""
            else:
                output_text = ""

            outputs[field_map[node_id]] = output_text
            cn_name = AGENT_NAMES_CN.get(node_id, node_id)
            queue.put(_sse_event("agent_complete", {
                "agent": node_id,
                "content": f"{cn_name} 已完成。",
                "full_text": output_text,
            }))

        # Save to S3 and update memory
        store = NovelStore()
        store.save_step1(user_id, novel_id, outputs["structure"], outputs["characters"], outputs["world"])
        memory_mgr.update_after_step(novel_id, 1, outputs)

        queue.put(_sse_event("step_complete", {
            "step": 1,
            "novel_id": novel_id,
            "content": "第一步完成！故事结构、角色和世界观已生成。",
        }))

    except Exception as e:
        logger.exception("Step 1 failed")
        queue.put(_sse_event("error", {"content": f"第一步错误：{str(e)}"}))

    finally:
        queue.put(_sse_event("done", {"content": "流结束"}))
        queue.put(_SENTINEL)


async def stream_step1(
    req: Step1Request, user_id: str
) -> AsyncIterator[bytes]:
    """Stream step 1 — structure, characters, world (parallel)."""
    store = NovelStore()

    if req.novel_id:
        novel_id = req.novel_id
        store.update_status(user_id, novel_id, "step1_draft")
    else:
        novel_id = store.create_novel(
            user_id,
            premise=req.premise,
            genre=req.genre.value,
            target_chapters=req.target_chapters,
        )

    prompt = _build_step1_prompt(req)

    # Yield the novel_id immediately
    yield _sse_event("pipeline_start", {
        "novel_id": novel_id,
        "content": "正在启动第一步：设计故事框架...",
    })

    queue: Queue[bytes | None] = Queue()
    thread = threading.Thread(
        target=_run_step1_in_thread,
        args=(prompt, novel_id, user_id, queue),
        daemon=True,
    )
    thread.start()

    async for event in _consume_queue(queue):
        yield event


# ── Step 2: plot weaving (single agent) ──────────────────────────────

def _build_step2_prompt(req: Step2Request) -> str:
    return f"""以下是第一步完成的故事基础素材：

**故事结构**：
{req.structure}

**角色档案**：
{req.characters}

**世界设定**：
{req.world}

请根据以上素材，编织详细的逐章情节大纲。所有创作内容必须使用简体中文。
"""


def _run_single_agent_in_thread(
    agent_name: str,
    system_prompt: str,
    model_fn,
    prompt: str,
    queue: Queue,
    post_fn=None,
):
    """Run a single agent in a thread, pushing streaming chunks to queue."""
    try:
        cn_name = AGENT_NAMES_CN.get(agent_name, agent_name)
        queue.put(_sse_event("agent_start", {
            "agent": agent_name,
            "content": f"{cn_name} 开始工作...",
        }))

        cb, flush, get_text = _make_streaming_callback_with_accumulator(agent_name, queue)
        agent = Agent(
            name=agent_name,
            model=model_fn(),
            system_prompt=system_prompt,
            tools=[],
            callback_handler=cb,
            hooks=[MaxTokensContinuationHook()],
        )

        result = agent(prompt)
        flush()

        # Prefer accumulated streamed text over result object
        output_text = get_text() or (str(result) if result else "")
        queue.put(_sse_event("agent_complete", {
            "agent": agent_name,
            "content": f"{cn_name} 已完成。",
            "full_text": output_text,
        }))

        # Run post-processing callback (e.g. save to S3)
        if post_fn:
            post_fn(output_text)

    except Exception as e:
        logger.exception("Agent %s failed", agent_name)
        queue.put(_sse_event("error", {"content": f"{agent_name} 错误：{str(e)}"}))

    finally:
        queue.put(_sse_event("done", {"content": "流结束"}))
        queue.put(_SENTINEL)


async def stream_step2(
    req: Step2Request, user_id: str
) -> AsyncIterator[bytes]:
    """Stream step 2 — plot weaving."""
    store = NovelStore()
    novel_id = req.novel_id
    store.update_status(user_id, novel_id, "step2_draft")

    # Load memory context and prepend to prompt
    memory_mgr = MemoryManager(user_id)
    memory_context = memory_mgr.format_context()
    prompt = _build_step2_prompt(req)
    if memory_context:
        prompt = memory_context + prompt

    yield _sse_event("pipeline_start", {
        "novel_id": novel_id,
        "content": "正在启动第二步：编织情节大纲...",
    })

    def save_plot(output_text: str):
        store.save_step2(user_id, novel_id, output_text)
        memory_mgr.update_after_step(novel_id, 2, {"plot": output_text})
        queue.put(_sse_event("step_complete", {
            "step": 2,
            "novel_id": novel_id,
            "content": "第二步完成！情节大纲已生成。",
        }))

    queue: Queue[bytes | None] = Queue()
    thread = threading.Thread(
        target=_run_single_agent_in_thread,
        args=("plot_weaver", PLOT_PROMPT, get_planning_model, prompt, queue, save_plot),
        daemon=True,
    )
    thread.start()

    async for event in _consume_queue(queue):
        yield event


# ── Step 3: write one chapter (prose_writer → editor) ────────────────

def _build_step3_prompt(req: Step3ChapterRequest, novel: dict) -> str:
    return f"""请写作第 {req.chapter_num} 章。

**本章大纲**：
{req.chapter_outline}

**写作风格**：{req.style.value}
**叙事视角**：{req.pov.value}

**故事结构**：
{novel.get('structure', '（无）')}

**角色档案**：
{novel.get('characters', '（无）')}

**世界设定**：
{novel.get('world', '（无）')}

**情节大纲**：
{novel.get('plot', '（无）')}

请根据以上信息写出完整的章节正文。所有创作内容必须使用简体中文。
"""


def _run_step3_in_thread(
    prompt: str, novel_id: str, user_id: str, chapter_num: int, queue: Queue
):
    """Run prose_writer then editor sequentially for one chapter."""
    try:
        store = NovelStore()
        memory_mgr = MemoryManager(user_id)

        # ── Prose writer ─────────────────────────────
        cn_pw = AGENT_NAMES_CN["prose_writer"]
        queue.put(_sse_event("agent_start", {
            "agent": "prose_writer",
            "content": f"{cn_pw} 开始写作第 {chapter_num} 章...",
        }))

        pw_cb, pw_flush, pw_get_text = _make_streaming_callback_with_accumulator("prose_writer", queue)
        pw_agent = Agent(
            name="prose_writer",
            model=get_creative_model(),
            system_prompt=PROSE_PROMPT,
            tools=[],
            callback_handler=pw_cb,
            hooks=[MaxTokensContinuationHook()],
        )

        pw_result = pw_agent(prompt)
        pw_flush()
        draft_text = pw_get_text() or (str(pw_result) if pw_result else "")

        queue.put(_sse_event("agent_complete", {
            "agent": "prose_writer",
            "content": f"{cn_pw} 初稿完成。",
            "full_text": draft_text,
        }))

        # ── Editor ───────────────────────────────────
        cn_ed = AGENT_NAMES_CN["editor"]
        queue.put(_sse_event("agent_start", {
            "agent": "editor",
            "content": f"{cn_ed} 开始润色第 {chapter_num} 章...",
        }))

        ed_cb, ed_flush, ed_get_text = _make_streaming_callback_with_accumulator("editor", queue)
        ed_agent = Agent(
            name="editor",
            model=get_model(),
            system_prompt=EDITOR_PROMPT,
            tools=[],
            callback_handler=ed_cb,
            hooks=[MaxTokensContinuationHook()],
        )

        editor_prompt = f"""以下是第 {chapter_num} 章的初稿，请进行编辑润色：

{draft_text}
"""
        ed_result = ed_agent(editor_prompt)
        ed_flush()
        final_text = ed_get_text() or (str(ed_result) if ed_result else draft_text)

        queue.put(_sse_event("agent_complete", {
            "agent": "editor",
            "content": f"{cn_ed} 润色完成。",
            "full_text": final_text,
        }))

        # Save chapter to S3 and update memory
        store.save_chapter(user_id, novel_id, chapter_num, final_text)
        memory_mgr.update_after_step(novel_id, 3, {"chapter_num": chapter_num})

        queue.put(_sse_event("step_complete", {
            "step": 3,
            "chapter_num": chapter_num,
            "novel_id": novel_id,
            "content": f"第 {chapter_num} 章写作完成！",
        }))

    except Exception as e:
        logger.exception("Step 3 chapter %d failed", chapter_num)
        queue.put(_sse_event("error", {"content": f"第 {chapter_num} 章写作错误：{str(e)}"}))

    finally:
        queue.put(_sse_event("done", {"content": "流结束"}))
        queue.put(_SENTINEL)


async def stream_step3_chapter(
    req: Step3ChapterRequest, user_id: str
) -> AsyncIterator[bytes]:
    """Stream step 3 — write and edit one chapter."""
    store = NovelStore()
    novel_id = req.novel_id
    novel = store.get_novel_full(user_id, novel_id)

    if not novel:
        yield _sse_event("error", {"content": "找不到该小说记录。"})
        yield _sse_event("done", {"content": "流结束"})
        return

    # Load memory context and prepend to prompt
    memory_mgr = MemoryManager(user_id)
    memory_context = memory_mgr.format_context()
    prompt = _build_step3_prompt(req, novel)
    if memory_context:
        prompt = memory_context + prompt

    yield _sse_event("pipeline_start", {
        "novel_id": novel_id,
        "content": f"正在启动第三步：写作第 {req.chapter_num} 章...",
    })

    queue: Queue[bytes | None] = Queue()
    thread = threading.Thread(
        target=_run_step3_in_thread,
        args=(prompt, novel_id, user_id, req.chapter_num, queue),
        daemon=True,
    )
    thread.start()

    async for event in _consume_queue(queue):
        yield event


# ── Chat: brainstorming agent ────────────────────────────────────────

def _run_chat_in_thread(
    message: str,
    history: list[dict],
    novel_id: str,
    user_id: str,
    queue: Queue,
):
    """Run a conversational brainstorming agent."""
    try:
        # Load memory context
        memory_mgr = MemoryManager(user_id)
        memory_context = memory_mgr.format_context()

        cb, flush, get_text = _make_streaming_callback_with_accumulator("chat", queue)
        agent = Agent(
            name="chat",
            model=get_model(),
            system_prompt=CHAT_SYSTEM_PROMPT,
            tools=[],
            callback_handler=cb,
        )

        # Build prompt with history context
        context_parts = []
        for msg in history[-20:]:  # Keep last 20 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                context_parts.append(f"用户：{content}")
            else:
                context_parts.append(f"顾问：{content}")

        if context_parts:
            full_prompt = "以下是之前的对话：\n" + "\n".join(context_parts) + f"\n\n用户：{message}"
        else:
            full_prompt = message

        # Prepend memory context
        if memory_context:
            full_prompt = memory_context + full_prompt

        result = agent(full_prompt)
        flush()

        output_text = get_text() or (str(result) if result else "")
        queue.put(_sse_event("agent_complete", {
            "agent": "chat",
            "content": "回复完成。",
        }))

        # Save chat history to novel record if we have a novel_id
        if novel_id:
            try:
                store = NovelStore()
                # Just update status, chat content is ephemeral
                store.update_status(user_id, novel_id, "chat")
            except Exception as e:
                logger.warning("Failed to update novel status: %s", e)

    except Exception as e:
        logger.exception("Chat agent failed")
        queue.put(_sse_event("error", {"content": f"聊天错误：{str(e)}"}))

    finally:
        queue.put(_sse_event("done", {"content": "流结束"}))
        queue.put(_SENTINEL)


async def stream_chat(
    req: ChatRequest, user_id: str
) -> AsyncIterator[bytes]:
    """Stream a brainstorming chat response."""
    store = NovelStore()
    novel_id = req.novel_id

    # Create novel record for new conversations
    if not novel_id:
        novel_id = store.create_novel(user_id, status="chat")

    yield _sse_event("pipeline_start", {
        "novel_id": novel_id,
        "content": "创意顾问思考中...",
    })

    queue: Queue[bytes | None] = Queue()
    thread = threading.Thread(
        target=_run_chat_in_thread,
        args=(req.message, req.history, novel_id, user_id, queue),
        daemon=True,
    )
    thread.start()

    async for event in _consume_queue(queue):
        yield event
