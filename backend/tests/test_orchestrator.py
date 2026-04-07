"""Tests for app.agents.orchestrator — build_prompt and build_novel_graph."""

import pytest
from unittest.mock import patch, MagicMock

from app.models.schemas import (
    NovelRequest,
    Genre,
    NarrativeStructure,
    WritingStyle,
    POV,
    CharacterBrief,
)


class TestBuildPrompt:
    """Test build_prompt() produces correct output for various NovelRequest configurations."""

    def test_basic_prompt(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(premise="A dragon learns to code")
        prompt = build_prompt(req)
        assert "A dragon learns to code" in prompt
        assert "Fantasy" in prompt
        assert "Three Act" in prompt
        assert "Commercial" in prompt
        assert "Third Limited" in prompt
        assert "12" in prompt  # target chapters default
        assert "engaging and immersive" in prompt

    def test_prompt_with_characters(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(
            premise="Heist in space",
            characters=[
                CharacterBrief(name="Zara", role="protagonist", description="Captain", motivation="Freedom"),
                CharacterBrief(name="Vex", role="antagonist", description="Corp CEO", motivation="Control"),
            ],
        )
        prompt = build_prompt(req)
        assert "Zara" in prompt
        assert "protagonist" in prompt
        assert "Freedom" in prompt
        assert "Vex" in prompt
        assert "antagonist" in prompt

    def test_prompt_no_characters_placeholder(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(premise="Solo journey")
        prompt = build_prompt(req)
        assert "Create appropriate characters" in prompt

    def test_prompt_custom_genre_and_structure(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(
            premise="Murder at a tech conference",
            genre=Genre.MYSTERY,
            structure=NarrativeStructure.FREYTAGS_PYRAMID,
            style=WritingStyle.DIALOGUE_HEAVY,
            pov=POV.FIRST_PERSON,
            target_chapters=25,
            setting_notes="Silicon Valley",
            theme_notes="Greed and ambition",
            tone="dark and witty",
        )
        prompt = build_prompt(req)
        assert "Mystery" in prompt
        assert "Freytags Pyramid" in prompt
        assert "Dialogue Heavy" in prompt
        assert "First Person" in prompt
        assert "25" in prompt
        assert "Silicon Valley" in prompt
        assert "Greed and ambition" in prompt
        assert "dark and witty" in prompt

    def test_prompt_empty_setting_and_theme(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(premise="Something", setting_notes="", theme_notes="")
        prompt = build_prompt(req)
        assert "Determine the best setting" in prompt
        assert "Identify the strongest thematic angle" in prompt


class TestBuildNovelGraph:
    """Test that build_novel_graph() creates a graph with correct structure."""

    @patch("app.agents.orchestrator.create_editor")
    @patch("app.agents.orchestrator.create_prose_writer")
    @patch("app.agents.orchestrator.create_plot_weaver")
    @patch("app.agents.orchestrator.create_world_builder")
    @patch("app.agents.orchestrator.create_character_developer")
    @patch("app.agents.orchestrator.create_story_architect")
    def test_graph_has_correct_agents(
        self, mock_arch, mock_char, mock_world, mock_plot, mock_prose, mock_edit
    ):
        # Each create_* returns a mock Agent
        mock_arch.return_value = MagicMock(name="story_architect")
        mock_char.return_value = MagicMock(name="character_developer")
        mock_world.return_value = MagicMock(name="world_builder")
        mock_plot.return_value = MagicMock(name="plot_weaver")
        mock_prose.return_value = MagicMock(name="prose_writer")
        mock_edit.return_value = MagicMock(name="editor")

        # Mock GraphBuilder so we can inspect calls
        with patch("app.agents.orchestrator.GraphBuilder") as MockGB:
            mock_builder = MagicMock()
            mock_graph = MagicMock()
            mock_builder.build.return_value = mock_graph
            MockGB.return_value = mock_builder

            from app.agents.orchestrator import build_novel_graph
            graph, agents = build_novel_graph()

            # Verify all 6 nodes were added
            assert mock_builder.add_node.call_count == 6
            node_names = [call.args[1] for call in mock_builder.add_node.call_args_list]
            assert "story_architect" in node_names
            assert "character_developer" in node_names
            assert "world_builder" in node_names
            assert "plot_weaver" in node_names
            assert "prose_writer" in node_names
            assert "editor" in node_names

            # Verify edges
            edge_calls = [
                (call.args[0], call.args[1])
                for call in mock_builder.add_edge.call_args_list
            ]
            assert ("story_architect", "plot_weaver") in edge_calls
            assert ("character_developer", "plot_weaver") in edge_calls
            assert ("world_builder", "plot_weaver") in edge_calls
            assert ("plot_weaver", "prose_writer") in edge_calls
            assert ("prose_writer", "editor") in edge_calls

            # Verify entry points
            entry_calls = [
                call.args[0] for call in mock_builder.set_entry_point.call_args_list
            ]
            assert "story_architect" in entry_calls
            assert "character_developer" in entry_calls
            assert "world_builder" in entry_calls

            # Verify agents dict
            assert set(agents.keys()) == {
                "story_architect", "character_developer", "world_builder",
                "plot_weaver", "prose_writer", "editor",
            }

            # Verify build was called
            mock_builder.build.assert_called_once()
            assert graph is mock_graph
