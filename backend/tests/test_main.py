"""Tests for FastAPI endpoints in app.main."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app


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
    def test_start_novel_calls_pipeline(self, client):
        mock_result = {
            "novel_id": "test-id",
            "status": "COMPLETED",
            "agents_completed": ["story_architect"],
        }
        with patch("app.main.run_novel_pipeline", new_callable=AsyncMock, return_value=mock_result):
            resp = client.post("/agent/invoke", json={
                "action": "start_novel",
                "payload": {"premise": "A wizard discovers time travel"},
                "user_id": "user123",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["result"]["novel_id"] == "test-id"

    def test_start_novel_invalid_payload(self, client):
        resp = client.post("/agent/invoke", json={
            "action": "start_novel",
            "payload": {"target_chapters": 999},  # missing premise, chapters out of range
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"


class TestAgentInvokeGenerateChapter:
    def test_generate_chapter_returns_ok(self, client):
        resp = client.post("/agent/invoke", json={
            "action": "generate_chapter",
            "payload": {"novel_id": "n1", "chapter_num": 3},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


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
