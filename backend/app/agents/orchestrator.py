"""Orchestrator — builds and runs the multi-agent Graph pipeline."""

from __future__ import annotations

import json
import uuid
import logging
from typing import Callable

import boto3
from strands import Agent
from strands.multiagent import GraphBuilder

from app.agents.story_architect import create_story_architect
from app.agents.character_dev import create_character_developer
from app.agents.world_builder import create_world_builder
from app.agents.plot_weaver import create_plot_weaver
from app.agents.prose_writer import create_prose_writer
from app.agents.editor import create_editor
from app.models.schemas import NovelRequest

logger = logging.getLogger(__name__)

AGENT_NAMES_CN = {
    "story_architect": "故事架构师",
    "character_developer": "角色开发师",
    "world_builder": "世界构建师",
    "plot_weaver": "情节编织师",
    "prose_writer": "文笔写手",
    "editor": "编辑",
}


def build_novel_graph() -> tuple:
    """Build the multi-agent graph for novel generation.

    Returns (graph, agent_dict) so callers can inspect agents.
    """
    architect = create_story_architect()
    character_dev = create_character_developer()
    world_builder = create_world_builder()
    plot_weaver = create_plot_weaver()
    prose_writer = create_prose_writer()
    editor = create_editor()

    builder = GraphBuilder()

    # Phase 1: Foundation agents (run in parallel as entry points)
    builder.add_node(architect, "story_architect")
    builder.add_node(character_dev, "character_developer")
    builder.add_node(world_builder, "world_builder")

    # Phase 2: Plot weaving (depends on all Phase 1 agents)
    builder.add_node(plot_weaver, "plot_weaver")
    builder.add_edge("story_architect", "plot_weaver")
    builder.add_edge("character_developer", "plot_weaver")
    builder.add_edge("world_builder", "plot_weaver")

    # Phase 3: Prose writing (depends on plot)
    builder.add_node(prose_writer, "prose_writer")
    builder.add_edge("plot_weaver", "prose_writer")

    # Phase 4: Editing (depends on prose)
    builder.add_node(editor, "editor")
    builder.add_edge("prose_writer", "editor")

    # Entry points — all three foundation agents
    builder.set_entry_point("story_architect")
    builder.set_entry_point("character_developer")
    builder.set_entry_point("world_builder")

    graph = builder.build()

    agents = {
        "story_architect": architect,
        "character_developer": character_dev,
        "world_builder": world_builder,
        "plot_weaver": plot_weaver,
        "prose_writer": prose_writer,
        "editor": editor,
    }

    return graph, agents


def build_prompt(req: NovelRequest) -> str:
    """Build the master prompt from the novel request."""
    chars_desc = ""
    if req.characters:
        chars_desc = "\n".join(
            f"- {c.name}（{c.role}）：{c.description} | 动机：{c.motivation}"
            for c in req.characters
        )
    else:
        chars_desc = "请根据故事前提和类型创建合适的角色。"

    return f"""请按照以下规格创作一部中文小说：

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

首先设计故事结构、开发角色和构建世界观。
然后编织情节、逐章写作，并进行编辑润色。
所有创作内容必须使用简体中文。
"""


async def run_novel_pipeline(
    req: NovelRequest,
    send_message: Callable,
    user_id: str = "system",
) -> dict:
    """Run the full novel generation pipeline with streaming updates.

    Args:
        req: The novel creation request.
        send_message: Async callback to stream messages to the client.
        user_id: The authenticated user ID.

    Returns:
        Summary dict with novel_id and metadata.
    """
    novel_id = str(uuid.uuid4())
    prompt = build_prompt(req)

    await send_message({
        "type": "pipeline_start",
        "novel_id": novel_id,
        "content": "正在启动小说生成流水线...",
    })

    graph, agents = build_novel_graph()

    shared_state = {
        "user_id": user_id,
        "novel_id": novel_id,
        "novel_request": req.model_dump(),
    }

    # Run the graph
    await send_message({
        "type": "agent_start",
        "agent": "story_architect,character_developer,world_builder",
        "content": "第一阶段：正在同步设计故事结构、开发角色和构建世界观...",
    })

    try:
        result = graph(prompt, invocation_state=shared_state)

        # Extract results from each node
        node_results = {}
        for node_id in ["story_architect", "character_developer", "world_builder",
                        "plot_weaver", "prose_writer", "editor"]:
            node_result = result.results.get(node_id)
            if node_result:
                node_results[node_id] = str(node_result.result)
                await send_message({
                    "type": "agent_result",
                    "agent": node_id,
                    "content": f"{AGENT_NAMES_CN.get(node_id, node_id)} 已完成。",
                    "data": {"preview": str(node_result.result)[:500]},
                })

        await send_message({
            "type": "novel_complete",
            "novel_id": novel_id,
            "content": "小说生成完成！",
            "data": {
                "novel_id": novel_id,
                "status": str(result.status),
                "agents_completed": list(node_results.keys()),
            },
        })

        return {
            "novel_id": novel_id,
            "status": str(result.status),
            "agents_completed": list(node_results.keys()),
        }

    except Exception as e:
        logger.exception("Pipeline failed")
        await send_message({
            "type": "error",
            "content": f"流水线错误：{str(e)}",
        })
        return {"novel_id": novel_id, "status": "FAILED", "error": str(e)}
