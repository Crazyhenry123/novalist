"""End-to-end integration test: traces the full request flow with Chinese params.

Flow: Client -> POST /agent/invoke (action=start_novel) -> BackgroundTasks ->
      run_novel_pipeline -> Graph agents -> post_to_connection messages
"""

import json
import uuid
from unittest.mock import patch, MagicMock, call

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import Genre, NarrativeStructure, WritingStyle


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def mock_apigw_client():
    """Mock boto3 API Gateway Management API client."""
    mock_client = MagicMock()
    mock_client.post_to_connection = MagicMock()
    return mock_client


@pytest.fixture()
def mock_graph_result():
    """Create a mock graph result with all 6 agents completed."""
    mock_node = MagicMock()
    mock_node.result = "模拟的小说内容片段，用于测试流水线。"

    result = MagicMock()
    result.status = "COMPLETED"
    result.results = {
        "story_architect": mock_node,
        "character_developer": mock_node,
        "world_builder": mock_node,
        "plot_weaver": mock_node,
        "prose_writer": mock_node,
        "editor": mock_node,
    }
    return result


class TestE2ENovelGeneration:
    """Full end-to-end test of the novel generation flow with Chinese parameters."""

    def test_full_flow_with_chinese_params(self, client, mock_apigw_client, mock_graph_result):
        """
        1. POST /agent/invoke with action=start_novel and Chinese params
        2. Endpoint returns immediately with status ok
        3. Background task runs the pipeline
        4. post_to_connection receives correct message sequence
        """
        mock_graph = MagicMock()
        mock_graph.return_value = mock_graph_result

        with patch("app.main.boto3") as mock_boto3_main, \
             patch("app.agents.orchestrator.build_novel_graph") as mock_build:

            mock_boto3_main.client.return_value = mock_apigw_client
            mock_build.return_value = (mock_graph, {})

            resp = client.post("/agent/invoke", json={
                "action": "start_novel",
                "payload": {
                    "premise": "一个现代程序员穿越到修仙世界",
                    "genre": "chuanyue",
                    "structure": "shuangwen",
                    "style": "shuangkuai",
                },
                "user_id": "test-user-001",
                "connection_id": "conn-abc-123",
                "callback_url": "https://execute-api.us-east-1.amazonaws.com/prod",
            })

            # 1. Endpoint returns immediately with "pipeline started"
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["message"] == "pipeline started"

            # 2. TestClient waits for background tasks, so post_to_connection was called
            assert mock_apigw_client.post_to_connection.called

            # 3. Extract all messages sent via post_to_connection
            ws_messages = []
            for c in mock_apigw_client.post_to_connection.call_args_list:
                raw = c.kwargs["Data"]
                msg = json.loads(raw.decode("utf-8"))
                ws_messages.append(msg)

            # 4. Verify message sequence: pipeline_start -> agent_start -> agent_results -> novel_complete
            types = [m["type"] for m in ws_messages]
            assert types[0] == "pipeline_start"
            assert types[1] == "agent_start"
            # 6 agent_result messages (one per agent)
            for i in range(2, 8):
                assert types[i] == "agent_result"
            assert types[8] == "novel_complete"

            # 5. Verify all messages contain Chinese text
            pipeline_start = ws_messages[0]
            assert "正在启动小说生成流水线" in pipeline_start["content"]

            agent_start = ws_messages[1]
            assert "第一阶段" in agent_start["content"]

            # Agent results should have Chinese agent names
            agent_result_contents = [ws_messages[i]["content"] for i in range(2, 8)]
            chinese_names = ["故事架构师", "角色开发师", "世界构建师", "情节编织师", "文笔写手", "编辑"]
            for name in chinese_names:
                assert any(name in c for c in agent_result_contents), f"Missing Chinese name: {name}"

            novel_complete = ws_messages[8]
            assert "小说生成完成" in novel_complete["content"]

            # 6. Verify novel_id is a valid UUID
            novel_id = pipeline_start["novel_id"]
            parsed = uuid.UUID(novel_id)
            assert str(parsed) == novel_id

            # novel_complete also has the same novel_id
            assert novel_complete["novel_id"] == novel_id
            assert novel_complete["data"]["novel_id"] == novel_id
            assert novel_complete["data"]["status"] == "COMPLETED"
            assert len(novel_complete["data"]["agents_completed"]) == 6

    def test_full_flow_connection_id_forwarded(self, client, mock_apigw_client, mock_graph_result):
        """Verify the connection_id is correctly passed to post_to_connection."""
        mock_graph = MagicMock()
        mock_graph.return_value = mock_graph_result

        with patch("app.main.boto3") as mock_boto3_main, \
             patch("app.agents.orchestrator.build_novel_graph") as mock_build:

            mock_boto3_main.client.return_value = mock_apigw_client
            mock_build.return_value = (mock_graph, {})

            client.post("/agent/invoke", json={
                "action": "start_novel",
                "payload": {"premise": "测试"},
                "connection_id": "my-conn-id",
                "callback_url": "https://example.com",
            })

            for c in mock_apigw_client.post_to_connection.call_args_list:
                assert c.kwargs["ConnectionId"] == "my-conn-id"

    def test_full_flow_pipeline_error_sends_error_message(self, client, mock_apigw_client):
        """If the graph raises, the client receives a Chinese error message."""
        mock_graph = MagicMock()
        mock_graph.side_effect = RuntimeError("Agent crashed")

        with patch("app.main.boto3") as mock_boto3_main, \
             patch("app.agents.orchestrator.build_novel_graph") as mock_build:

            mock_boto3_main.client.return_value = mock_apigw_client
            mock_build.return_value = (mock_graph, {})

            resp = client.post("/agent/invoke", json={
                "action": "start_novel",
                "payload": {"premise": "测试失败流程"},
                "connection_id": "conn-err",
                "callback_url": "https://example.com",
            })

            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

            ws_messages = []
            for c in mock_apigw_client.post_to_connection.call_args_list:
                raw = c.kwargs["Data"]
                msg = json.loads(raw.decode("utf-8"))
                ws_messages.append(msg)

            types = [m["type"] for m in ws_messages]
            # pipeline_start, agent_start sent before graph call,
            # then error from the exception
            assert "pipeline_start" in types
            assert "error" in types

            error_msgs = [m for m in ws_messages if m["type"] == "error"]
            assert len(error_msgs) >= 1
            # The error from orchestrator contains Chinese
            assert any("流水线错误" in m["content"] for m in error_msgs)

    def test_invalid_chinese_genre_rejected(self, client):
        """An invalid genre value is rejected."""
        resp = client.post("/agent/invoke", json={
            "action": "start_novel",
            "payload": {
                "premise": "测试",
                "genre": "invalid_genre",
            },
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
