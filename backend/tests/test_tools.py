"""Tests for app.tools.story_tools — save/load with mocked DynamoDB."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_ddb():
    """Create a mock DynamoDB resource and tables."""
    mock_novels_table = MagicMock()
    mock_chapters_table = MagicMock()
    mock_resource = MagicMock()

    def table_router(name):
        if name == "novalist-novels":
            return mock_novels_table
        elif name == "novalist-chapters":
            return mock_chapters_table
        return MagicMock()

    mock_resource.Table.side_effect = table_router

    with patch("app.tools.story_tools.boto3") as mock_boto3:
        mock_boto3.resource.return_value = mock_resource
        yield {
            "novels_table": mock_novels_table,
            "chapters_table": mock_chapters_table,
            "boto3": mock_boto3,
        }


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext with invocation_state."""
    ctx = MagicMock()
    ctx.invocation_state = {"user_id": "test-user", "novel_id": "novel-123"}
    return ctx


def _call_tool(tool, **kwargs):
    """Call the underlying function of a strands @tool-decorated function."""
    return tool._tool_func(**kwargs)


class TestSaveStoryElement:
    def test_saves_structure(self, mock_ddb, mock_tool_context):
        from app.tools.story_tools import save_story_element
        result = _call_tool(
            save_story_element,
            novel_id="novel-123",
            element_type="structure",
            element_data='{"title": "Test Novel"}',
            tool_context=mock_tool_context,
        )
        assert "Saved structure" in result
        assert "novel-123" in result
        mock_ddb["novels_table"].update_item.assert_called_once()
        call_kwargs = mock_ddb["novels_table"].update_item.call_args[1]
        assert call_kwargs["Key"] == {"user_id": "test-user", "novel_id": "novel-123"}
        assert call_kwargs["ExpressionAttributeNames"] == {"#el": "structure"}

    def test_saves_characters(self, mock_ddb, mock_tool_context):
        from app.tools.story_tools import save_story_element
        result = _call_tool(
            save_story_element,
            novel_id="novel-123",
            element_type="characters",
            element_data='[{"name": "Alice"}]',
            tool_context=mock_tool_context,
        )
        assert "Saved characters" in result

    def test_uses_system_default_user(self, mock_ddb):
        ctx = MagicMock()
        ctx.invocation_state = {}  # no user_id
        from app.tools.story_tools import save_story_element
        _call_tool(
            save_story_element,
            novel_id="n1",
            element_type="world",
            element_data="{}",
            tool_context=ctx,
        )
        call_kwargs = mock_ddb["novels_table"].update_item.call_args[1]
        assert call_kwargs["Key"]["user_id"] == "system"


class TestSaveChapter:
    def test_saves_chapter(self, mock_ddb, mock_tool_context):
        from app.tools.story_tools import save_chapter
        result = _call_tool(
            save_chapter,
            novel_id="novel-123",
            chapter_num=1,
            title="The Beginning",
            content="It was a dark and stormy night. The wind howled.",
            summary="Introduction to the story.",
            tool_context=mock_tool_context,
        )
        assert "Saved chapter 1" in result
        assert "The Beginning" in result
        assert "10 words" in result
        mock_ddb["chapters_table"].put_item.assert_called_once()
        item = mock_ddb["chapters_table"].put_item.call_args[1]["Item"]
        assert item["novel_id"] == "novel-123"
        assert item["chapter_num"] == 1
        assert item["title"] == "The Beginning"
        assert item["word_count"] == 10

    def test_empty_content_zero_words(self, mock_ddb, mock_tool_context):
        from app.tools.story_tools import save_chapter
        _call_tool(
            save_chapter,
            novel_id="novel-123",
            chapter_num=2,
            title="Empty",
            content="",
            summary="Nothing here.",
            tool_context=mock_tool_context,
        )
        item = mock_ddb["chapters_table"].put_item.call_args[1]["Item"]
        assert item["word_count"] == 0


class TestLoadStoryElement:
    def test_loads_existing_element(self, mock_ddb, mock_tool_context):
        mock_ddb["novels_table"].get_item.return_value = {
            "Item": {
                "user_id": "test-user",
                "novel_id": "novel-123",
                "structure": '{"title": "My Novel"}',
            }
        }
        from app.tools.story_tools import load_story_element
        result = _call_tool(
            load_story_element,
            novel_id="novel-123",
            element_type="structure",
            tool_context=mock_tool_context,
        )
        assert result == '{"title": "My Novel"}'
        mock_ddb["novels_table"].get_item.assert_called_once_with(
            Key={"user_id": "test-user", "novel_id": "novel-123"}
        )

    def test_loads_missing_element_returns_empty_json(self, mock_ddb, mock_tool_context):
        mock_ddb["novels_table"].get_item.return_value = {
            "Item": {
                "user_id": "test-user",
                "novel_id": "novel-123",
            }
        }
        from app.tools.story_tools import load_story_element
        result = _call_tool(
            load_story_element,
            novel_id="novel-123",
            element_type="plot",
            tool_context=mock_tool_context,
        )
        assert result == "{}"

    def test_loads_missing_item_returns_empty_json(self, mock_ddb, mock_tool_context):
        mock_ddb["novels_table"].get_item.return_value = {}  # no Item key
        from app.tools.story_tools import load_story_element
        result = _call_tool(
            load_story_element,
            novel_id="novel-123",
            element_type="structure",
            tool_context=mock_tool_context,
        )
        assert result == "{}"
