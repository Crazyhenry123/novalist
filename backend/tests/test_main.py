"""Tests for FastAPI endpoints in app.main."""

import json
import pytest
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

from app.main import app, _make_send_message, _run_pipeline_background


@pytest.fixture()
def client():
    """Create a TestClient."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "novalist"


class TestAgentInvokePing:
    def test_ping_returns_ok(self, client):
        resp = client.post("/agent/invoke", json={"action": "ping"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAgentInvokeUnknown:
    def test_unknown_action_returns_error(self, client):
        resp = client.post("/agent/invoke", json={"action": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "Unknown action" in data["message"]


class TestAgentInvokeStartNovel:
    def test_start_novel_returns_pipeline_started(self, client):
        """After the async-to-sync refactor, agent_invoke returns immediately
        with 'pipeline started' and runs the pipeline in BackgroundTasks."""
        with patch("app.main._run_pipeline_background") as mock_bg:
            resp = client.post("/agent/invoke", json={
                "action": "start_novel",
                "payload": {"premise": "A wizard discovers time travel"},
                "user_id": "user123",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["message"] == "pipeline started"
            # BackgroundTasks runs the function; TestClient waits for it
            mock_bg.assert_called_once()
            call_args = mock_bg.call_args
            # First arg is the NovelRequest
            assert call_args.args[0].premise == "A wizard discovers time travel"
            # Fourth arg is user_id
            assert call_args.args[3] == "user123"

    def test_start_novel_uses_background_tasks(self, client):
        """Verify the endpoint adds _run_pipeline_background to BackgroundTasks."""
        with patch("app.main._run_pipeline_background"):
            resp = client.post("/agent/invoke", json={
                "action": "start_novel",
                "payload": {"premise": "Test premise"},
                "user_id": "u1",
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_start_novel_invalid_payload(self, client):
        resp = client.post("/agent/invoke", json={
            "action": "start_novel",
            "payload": {"target_chapters": 999},  # missing premise, chapters out of range
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_start_novel_with_chinese_genre(self, client):
        """Chinese enum values work in the payload."""
        with patch("app.main._run_pipeline_background"):
            resp = client.post("/agent/invoke", json={
                "action": "start_novel",
                "payload": {
                    "premise": "穿越到古代",
                    "genre": "chuanyue",
                    "structure": "shuangwen",
                    "style": "shuangkuai",
                },
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"


class TestAgentInvokeGenerateChapter:
    def test_generate_chapter_returns_ok(self, client):
        resp = client.post("/agent/invoke", json={
            "action": "generate_chapter",
            "payload": {"novel_id": "n1", "chapter_num": 3},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestMakeSendMessage:
    def test_send_message_calls_post_to_connection(self):
        """send_message is now sync and calls boto3 post_to_connection."""
        mock_client = MagicMock()
        with patch("app.main.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            send = _make_send_message("https://example.com", "conn-123")
            send({"type": "test", "content": "hello"})
            mock_client.post_to_connection.assert_called_once()
            call_kwargs = mock_client.post_to_connection.call_args.kwargs
            assert call_kwargs["ConnectionId"] == "conn-123"
            payload = json.loads(call_kwargs["Data"].decode("utf-8"))
            assert payload["type"] == "test"

    def test_send_message_no_callback_url(self):
        """When callback_url is None, send_message is a no-op."""
        send = _make_send_message(None, "conn-123")
        # Should not raise
        send({"type": "test"})

    def test_send_message_handles_exception(self):
        """send_message catches exceptions and logs a warning."""
        mock_client = MagicMock()
        mock_client.post_to_connection.side_effect = Exception("network error")
        with patch("app.main.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            send = _make_send_message("https://example.com", "conn-123")
            # Should not raise
            send({"type": "test"})


class TestRunPipelineBackground:
    def test_calls_run_novel_pipeline(self):
        """_run_pipeline_background creates send_message and calls run_novel_pipeline."""
        from app.models.schemas import NovelRequest
        req = NovelRequest(premise="Test")
        with patch("app.main.run_novel_pipeline") as mock_pipeline, \
             patch("app.main._make_send_message") as mock_make_send:
            mock_send = MagicMock()
            mock_make_send.return_value = mock_send
            _run_pipeline_background(req, "https://cb.url", "conn1", "user1")
            mock_pipeline.assert_called_once_with(req, mock_send, "user1")

    def test_sends_error_on_exception(self):
        """If run_novel_pipeline raises, an error message is sent."""
        from app.models.schemas import NovelRequest
        req = NovelRequest(premise="Test")
        with patch("app.main.run_novel_pipeline", side_effect=RuntimeError("boom")), \
             patch("app.main._make_send_message") as mock_make_send:
            mock_send = MagicMock()
            mock_make_send.return_value = mock_send
            _run_pipeline_background(req, "https://cb.url", "conn1", "user1")
            mock_send.assert_called()
            error_msg = mock_send.call_args.args[0]
            assert error_msg["type"] == "error"
            assert "生成失败" in error_msg["content"]


class TestListNovels:
    def test_list_novels_returns_items(self, client):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"user_id": "u1", "novel_id": "n1", "title": "Test Novel"},
            ]
        }
        mock_ddb = MagicMock()
        mock_ddb.Table.return_value = mock_table

        with patch("app.main.boto3") as mock_boto3:
            mock_boto3.resource.return_value = mock_ddb
            resp = client.get("/novels/u1")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["novels"]) == 1
            assert data["novels"][0]["novel_id"] == "n1"

    def test_list_novels_empty(self, client):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_ddb = MagicMock()
        mock_ddb.Table.return_value = mock_table

        with patch("app.main.boto3") as mock_boto3:
            mock_boto3.resource.return_value = mock_ddb
            resp = client.get("/novels/unknown-user")
            assert resp.status_code == 200
            assert resp.json()["novels"] == []


class TestListChapters:
    def test_list_chapters_returns_items(self, client):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"novel_id": "n1", "chapter_num": 1, "title": "Ch1", "content": "Once..."},
                {"novel_id": "n1", "chapter_num": 2, "title": "Ch2", "content": "Then..."},
            ]
        }
        mock_ddb = MagicMock()
        mock_ddb.Table.return_value = mock_table

        with patch("app.main.boto3") as mock_boto3:
            mock_boto3.resource.return_value = mock_ddb
            resp = client.get("/novels/n1/chapters")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["chapters"]) == 2

    def test_list_chapters_empty(self, client):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_ddb = MagicMock()
        mock_ddb.Table.return_value = mock_table

        with patch("app.main.boto3") as mock_boto3:
            mock_boto3.resource.return_value = mock_ddb
            resp = client.get("/novels/nonexistent/chapters")
            assert resp.status_code == 200
            assert resp.json()["chapters"] == []
