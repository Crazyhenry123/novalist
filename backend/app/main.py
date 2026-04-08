"""FastAPI application — backend for Novalist multi-agent novel writer."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

import boto3
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.auth import verify_token
from app.models.schemas import NovelRequest
from app.agents.orchestrator import run_novel_pipeline

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Novalist backend starting")
    yield
    logger.info("Novalist backend shutting down")


app = FastAPI(title="Novalist", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "novalist"}


def _make_send_message(callback_url: str | None, connection_id: str | None):
    """Create a sync send_message callback that posts to API Gateway WebSocket."""
    apigw = None
    if callback_url:
        apigw = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=callback_url,
        )

    def send_message(msg: dict):
        if apigw and connection_id:
            try:
                apigw.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps(msg, ensure_ascii=False).encode("utf-8"),
                )
            except Exception as e:
                logger.warning(f"Failed to send WS message: {e}")

    return send_message


def _run_pipeline_background(
    novel_req: NovelRequest,
    callback_url: str | None,
    connection_id: str | None,
    user_id: str,
):
    """Run the novel pipeline in the background, streaming results to the client.
    Called by FastAPI BackgroundTasks in a threadpool."""
    send_message = _make_send_message(callback_url, connection_id)
    try:
        run_novel_pipeline(novel_req, send_message, user_id)
    except Exception as e:
        logger.exception("Background pipeline failed")
        send_message({"type": "error", "content": f"生成失败：{str(e)}"})


@app.post("/agent/invoke")
async def agent_invoke(request: Request, background_tasks: BackgroundTasks):
    """Called by the WebSocket Lambda to process a novel generation request.

    Returns immediately. The pipeline runs in the background and streams
    results directly to the client via API Gateway Management API.
    """
    body = await request.json()
    action = body.get("action", "")
    connection_id = body.get("connection_id")
    callback_url = body.get("callback_url")
    send_message = _make_send_message(callback_url, connection_id)

    if action == "start_novel":
        payload = body.get("payload", {})
        try:
            novel_req = NovelRequest(**payload)
        except Exception as e:
            send_message({"type": "error", "content": f"请求无效：{e}"})
            return {"status": "error", "message": str(e)}

        user_id = body.get("user_id", "system")

        # Run pipeline in background — return HTTP 200 immediately
        background_tasks.add_task(
            _run_pipeline_background, novel_req, callback_url, connection_id, user_id
        )
        return {"status": "ok", "message": "pipeline started"}

    elif action == "generate_chapter":
        payload = body.get("payload", {})
        novel_id = payload.get("novel_id")
        chapter_num = payload.get("chapter_num", 1)
        send_message({
            "type": "info",
            "content": f"第{chapter_num}章生成（小说 {novel_id}）——请使用 start_novel 启动完整流水线。",
        })
        return {"status": "ok"}

    elif action == "ping":
        send_message({"type": "pong", "content": "alive"})
        return {"status": "ok"}

    else:
        send_message({"type": "error", "content": f"未知操作：{action}"})
        return {"status": "error", "message": f"Unknown action: {action}"}


@app.get("/novels/{user_id}")
async def list_novels(user_id: str):
    """List all novels for a user."""
    ddb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = ddb.Table(settings.novels_table)
    resp = table.query(
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    return {"novels": resp.get("Items", [])}


@app.get("/novels/{novel_id}/chapters")
async def list_chapters(novel_id: str):
    """List all chapters for a novel."""
    ddb = boto3.resource("dynamodb", region_name=settings.aws_region)
    table = ddb.Table(settings.chapters_table)
    resp = table.query(
        KeyConditionExpression="novel_id = :nid",
        ExpressionAttributeValues={":nid": novel_id},
    )
    return {"chapters": resp.get("Items", [])}
