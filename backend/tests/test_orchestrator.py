"""Tests for app.agents.orchestrator — build_prompt, build_novel_graph, run_novel_pipeline."""

import pytest
from unittest.mock import patch, MagicMock, call

from app.models.schemas import (
    NovelRequest,
    Genre,
    NarrativeStructure,
    WritingStyle,
    POV,
    CharacterBrief,
)


class TestBuildPrompt:
    """Test build_prompt() produces correct Chinese output for various NovelRequest configs."""

    def test_basic_prompt_defaults(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(premise="A dragon learns to code")
        prompt = build_prompt(req)
        assert "A dragon learns to code" in prompt
        # Default genre is XUANHUAN, so the value is "xuanhuan"
        assert "xuanhuan" in prompt
        assert "three_act" in prompt
        assert "commercial" in prompt
        assert "third_limited" in prompt
        assert "12" in prompt  # target chapters default
        # Default tone is Chinese now
        assert "引人入胜" in prompt

    def test_prompt_with_characters(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(
            premise="太空中的大劫案",
            characters=[
                CharacterBrief(name="Zara", role="主角", description="舰长", motivation="自由"),
                CharacterBrief(name="Vex", role="反派", description="集团CEO", motivation="控制"),
            ],
        )
        prompt = build_prompt(req)
        assert "Zara" in prompt
        assert "主角" in prompt
        assert "自由" in prompt
        assert "Vex" in prompt
        assert "反派" in prompt

    def test_prompt_no_characters_placeholder(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(premise="独自旅行")
        prompt = build_prompt(req)
        # Chinese placeholder for no characters
        assert "请根据故事前提和类型创建合适的角色" in prompt

    def test_prompt_custom_genre_and_structure(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(
            premise="技术大会上的谋杀案",
            genre=Genre.MYSTERY,
            structure=NarrativeStructure.FREYTAGS_PYRAMID,
            style=WritingStyle.DIALOGUE_HEAVY,
            pov=POV.FIRST_PERSON,
            target_chapters=25,
            setting_notes="硅谷",
            theme_notes="贪婪与野心",
            tone="黑暗而机智",
        )
        prompt = build_prompt(req)
        assert "mystery" in prompt
        assert "freytags_pyramid" in prompt
        assert "dialogue_heavy" in prompt
        assert "first_person" in prompt
        assert "25" in prompt
        assert "硅谷" in prompt
        assert "贪婪与野心" in prompt
        assert "黑暗而机智" in prompt

    def test_prompt_chinese_genre_values(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(
            premise="穿越到古代",
            genre=Genre.CHUANYUE,
            structure=NarrativeStructure.SHUANGWEN,
            style=WritingStyle.SHUANGKUAI,
        )
        prompt = build_prompt(req)
        assert "chuanyue" in prompt
        assert "shuangwen" in prompt
        assert "shuangkuai" in prompt

    def test_prompt_empty_setting_and_theme(self):
        from app.agents.orchestrator import build_prompt
        req = NovelRequest(premise="Something", setting_notes="", theme_notes="")
        prompt = build_prompt(req)
        # Chinese placeholders
        assert "请根据前提确定最佳设定" in prompt
        assert "请挖掘最有力的主题角度" in prompt


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
        mock_arch.return_value = MagicMock(name="story_architect")
        mock_char.return_value = MagicMock(name="character_developer")
        mock_world.return_value = MagicMock(name="world_builder")
        mock_plot.return_value = MagicMock(name="plot_weaver")
        mock_prose.return_value = MagicMock(name="prose_writer")
        mock_edit.return_value = MagicMock(name="editor")

        with patch("app.agents.orchestrator.GraphBuilder") as MockGB:
            mock_builder = MagicMock()
            mock_graph = MagicMock()
            mock_builder.build.return_value = mock_graph
            MockGB.return_value = mock_builder

            from app.agents.orchestrator import build_novel_graph
            graph, agents = build_novel_graph()

            assert mock_builder.add_node.call_count == 6
            node_names = [call.args[1] for call in mock_builder.add_node.call_args_list]
            assert "story_architect" in node_names
            assert "character_developer" in node_names
            assert "world_builder" in node_names
            assert "plot_weaver" in node_names
            assert "prose_writer" in node_names
            assert "editor" in node_names

            edge_calls = [
                (call.args[0], call.args[1])
                for call in mock_builder.add_edge.call_args_list
            ]
            assert ("story_architect", "plot_weaver") in edge_calls
            assert ("character_developer", "plot_weaver") in edge_calls
            assert ("world_builder", "plot_weaver") in edge_calls
            assert ("plot_weaver", "prose_writer") in edge_calls
            assert ("prose_writer", "editor") in edge_calls

            entry_calls = [
                call.args[0] for call in mock_builder.set_entry_point.call_args_list
            ]
            assert "story_architect" in entry_calls
            assert "character_developer" in entry_calls
            assert "world_builder" in entry_calls

            assert set(agents.keys()) == {
                "story_architect", "character_developer", "world_builder",
                "plot_weaver", "prose_writer", "editor",
            }

            mock_builder.build.assert_called_once()
            assert graph is mock_graph


class TestRunNovelPipeline:
    """Test run_novel_pipeline is sync and produces correct messages."""

    @patch("app.agents.orchestrator.build_novel_graph")
    def test_pipeline_is_sync_and_sends_messages(self, mock_build_graph):
        """run_novel_pipeline is a regular sync function (not async)."""
        from app.agents.orchestrator import run_novel_pipeline
        import inspect
        assert not inspect.iscoroutinefunction(run_novel_pipeline)

    @patch("app.agents.orchestrator.build_novel_graph")
    def test_pipeline_sends_correct_sequence(self, mock_build_graph):
        """Pipeline sends pipeline_start, agent_start, agent_result(s), novel_complete."""
        from app.agents.orchestrator import run_novel_pipeline

        # Build mock graph result
        mock_node_result = MagicMock()
        mock_node_result.result = "模拟结果内容"

        mock_graph_result = MagicMock()
        mock_graph_result.status = "COMPLETED"
        mock_graph_result.results = {
            "story_architect": mock_node_result,
            "character_developer": mock_node_result,
            "world_builder": mock_node_result,
            "plot_weaver": mock_node_result,
            "prose_writer": mock_node_result,
            "editor": mock_node_result,
        }

        mock_graph = MagicMock()
        mock_graph.return_value = mock_graph_result
        mock_build_graph.return_value = (mock_graph, {})

        send = MagicMock()
        req = NovelRequest(premise="测试前提")

        result = run_novel_pipeline(req, send, "user1")

        # Check return value
        assert "novel_id" in result
        assert result["status"] == "COMPLETED"
        assert len(result["agents_completed"]) == 6

        # Check message sequence
        messages = [c.args[0] for c in send.call_args_list]
        types = [m["type"] for m in messages]
        assert types[0] == "pipeline_start"
        assert types[1] == "agent_start"
        # 6 agent_result messages
        assert types[2:8] == ["agent_result"] * 6
        assert types[8] == "novel_complete"

    @patch("app.agents.orchestrator.build_novel_graph")
    def test_pipeline_sends_chinese_messages(self, mock_build_graph):
        """All messages contain Chinese text."""
        from app.agents.orchestrator import run_novel_pipeline

        mock_node_result = MagicMock()
        mock_node_result.result = "内容"

        mock_graph_result = MagicMock()
        mock_graph_result.status = "COMPLETED"
        mock_graph_result.results = {
            "story_architect": mock_node_result,
        }

        mock_graph = MagicMock()
        mock_graph.return_value = mock_graph_result
        mock_build_graph.return_value = (mock_graph, {})

        send = MagicMock()
        req = NovelRequest(premise="测试")

        run_novel_pipeline(req, send, "user1")

        messages = [c.args[0] for c in send.call_args_list]
        # pipeline_start has Chinese
        assert "正在启动小说生成流水线" in messages[0]["content"]
        # agent_start has Chinese
        assert "第一阶段" in messages[1]["content"]
        # agent_result has Chinese agent name
        assert "故事架构师" in messages[2]["content"]
        # novel_complete has Chinese
        assert "小说生成完成" in messages[3]["content"]

    @patch("app.agents.orchestrator.build_novel_graph")
    def test_pipeline_handles_graph_exception(self, mock_build_graph):
        """If graph raises, pipeline sends error message and returns FAILED."""
        from app.agents.orchestrator import run_novel_pipeline

        mock_graph = MagicMock()
        mock_graph.side_effect = RuntimeError("graph crashed")
        mock_build_graph.return_value = (mock_graph, {})

        send = MagicMock()
        req = NovelRequest(premise="测试")

        result = run_novel_pipeline(req, send, "user1")
        assert result["status"] == "FAILED"
        assert "graph crashed" in result["error"]

        # Error message sent
        messages = [c.args[0] for c in send.call_args_list]
        error_msgs = [m for m in messages if m["type"] == "error"]
        assert len(error_msgs) == 1
        assert "流水线错误" in error_msgs[0]["content"]
