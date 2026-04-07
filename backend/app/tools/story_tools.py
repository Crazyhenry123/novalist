"""Tools available to agents for persisting and retrieving story elements."""

import json
import boto3
from strands import tool
from strands.types.tools import ToolContext
from app.config import settings


@tool(context=True)
def save_story_element(
    novel_id: str, element_type: str, element_data: str, tool_context: ToolContext
) -> str:
    """Save a story element (structure, character, world, plot, chapter) to the novel's record.

    Args:
        novel_id: The unique novel identifier.
        element_type: One of 'structure', 'characters', 'world', 'plot', 'chapter'.
        element_data: JSON string of the element data to save.
    """
    ddb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = ddb.Table(settings.novels_table)
    user_id = tool_context.invocation_state.get("user_id", "system")

    table.update_item(
        Key={"user_id": user_id, "novel_id": novel_id},
        UpdateExpression="SET #el = :val",
        ExpressionAttributeNames={"#el": element_type},
        ExpressionAttributeValues={":val": element_data},
    )
    return f"Saved {element_type} for novel {novel_id}"


@tool(context=True)
def save_chapter(
    novel_id: str,
    chapter_num: int,
    title: str,
    content: str,
    summary: str,
    tool_context: ToolContext,
) -> str:
    """Save a completed chapter draft to storage.

    Args:
        novel_id: The unique novel identifier.
        chapter_num: Chapter number (1-based).
        title: Chapter title.
        content: Full chapter prose content.
        summary: Brief summary of the chapter.
    """
    ddb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = ddb.Table(settings.chapters_table)

    table.put_item(
        Item={
            "novel_id": novel_id,
            "chapter_num": chapter_num,
            "title": title,
            "content": content,
            "summary": summary,
            "word_count": len(content.split()),
        }
    )
    return f"Saved chapter {chapter_num}: {title} ({len(content.split())} words)"


@tool(context=True)
def load_story_element(
    novel_id: str, element_type: str, tool_context: ToolContext
) -> str:
    """Load a previously saved story element.

    Args:
        novel_id: The unique novel identifier.
        element_type: One of 'structure', 'characters', 'world', 'plot'.
    """
    ddb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = ddb.Table(settings.novels_table)
    user_id = tool_context.invocation_state.get("user_id", "system")

    resp = table.get_item(Key={"user_id": user_id, "novel_id": novel_id})
    item = resp.get("Item", {})
    return item.get(element_type, "{}")
