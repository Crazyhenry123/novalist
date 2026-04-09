"""FastAPI application — backend for Novalist v2 step-based novel composition."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models.schemas import (
    Step1Request,
    Step2Request,
    Step3ChapterRequest,
    ChatRequest,
    SaveStep1Request,
    SaveStep2Request,
)
from app.models.novel_store import NovelStore
from app.agents.orchestrator import (
    stream_step1,
    stream_step2,
    stream_step3_chapter,
    stream_chat,
)

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Novalist backend starting")
    yield
    logger.info("Novalist backend shutting down")


app = FastAPI(title="Novalist", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"],
)


# ── Health ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "novalist"}


# ── SSE streaming endpoints ─────────────────────────────────────────

def _get_user_id(request: Request) -> str:
    return request.query_params.get("user_id", "anonymous")


@app.post("/api/step1")
async def step1(request: Request):
    """Stream step 1: generate structure, characters, world in parallel."""
    body = await request.json()
    user_id = _get_user_id(request)
    logger.info("Step 1 request from user %s", user_id)

    try:
        req = Step1Request(**body)
    except Exception as e:
        logger.error("Invalid step1 request: %s", e)
        return {"status": "error", "message": f"请求无效：{e}"}

    return StreamingResponse(
        stream_step1(req, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/step2")
async def step2(request: Request):
    """Stream step 2: generate plot outline from step 1 results."""
    body = await request.json()
    user_id = _get_user_id(request)
    logger.info("Step 2 request from user %s", user_id)

    try:
        req = Step2Request(**body)
    except Exception as e:
        logger.error("Invalid step2 request: %s", e)
        return {"status": "error", "message": f"请求无效：{e}"}

    return StreamingResponse(
        stream_step2(req, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/step3/chapter")
async def step3_chapter(request: Request):
    """Stream step 3: write and edit one chapter."""
    body = await request.json()
    user_id = _get_user_id(request)
    logger.info("Step 3 chapter request from user %s", user_id)

    try:
        req = Step3ChapterRequest(**body)
    except Exception as e:
        logger.error("Invalid step3 request: %s", e)
        return {"status": "error", "message": f"请求无效：{e}"}

    return StreamingResponse(
        stream_step3_chapter(req, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat(request: Request):
    """Stream a brainstorming chat response."""
    body = await request.json()
    user_id = _get_user_id(request)
    logger.info("Chat request from user %s", user_id)

    try:
        req = ChatRequest(**body)
    except Exception as e:
        logger.error("Invalid chat request: %s", e)
        return {"status": "error", "message": f"请求无效：{e}"}

    return StreamingResponse(
        stream_chat(req, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ── REST endpoints for saving edits and reading state ────────────────

@app.put("/api/novel/{novel_id}/step1")
async def save_step1(novel_id: str, request: Request):
    """Save user edits to step 1 results."""
    body = await request.json()
    user_id = _get_user_id(request)
    logger.info("Save step1 for novel %s, user %s", novel_id, user_id)

    try:
        req = SaveStep1Request(**body)
    except Exception as e:
        return {"status": "error", "message": f"请求无效：{e}"}

    store = NovelStore()
    store.save_step1(user_id, novel_id, req.structure, req.characters, req.world)
    novel = store.get_novel_full(user_id, novel_id)
    return novel


@app.put("/api/novel/{novel_id}/step2")
async def save_step2(novel_id: str, request: Request):
    """Save user edits to step 2 results."""
    body = await request.json()
    user_id = _get_user_id(request)
    logger.info("Save step2 for novel %s, user %s", novel_id, user_id)

    try:
        req = SaveStep2Request(**body)
    except Exception as e:
        return {"status": "error", "message": f"请求无效：{e}"}

    store = NovelStore()
    store.save_step2(user_id, novel_id, req.plot)
    novel = store.get_novel_full(user_id, novel_id)
    return novel


@app.get("/api/novels")
async def list_novels(request: Request):
    """List all novels for a user (DynamoDB index only, no S3)."""
    user_id = _get_user_id(request)
    store = NovelStore()
    novels = store.list_novels(user_id)
    return {"novels": novels}


@app.get("/api/novel/{novel_id}")
async def get_novel(novel_id: str, request: Request):
    """Get full novel state including S3 content and chapters."""
    user_id = _get_user_id(request)
    store = NovelStore()
    novel = store.get_novel_full(user_id, novel_id)
    if not novel:
        return {"status": "error", "message": "小说不存在"}
    return novel


# ── Memory endpoints ─────────────────────────────────────────────────

@app.get("/api/memory")
async def get_memory(request: Request):
    """Get the user's session memory."""
    user_id = _get_user_id(request)
    from app.models.memory import MemoryManager
    mgr = MemoryManager(user_id)
    return mgr.load()


@app.put("/api/memory")
async def update_memory(request: Request):
    """Update the user's session memory."""
    user_id = _get_user_id(request)
    body = await request.json()
    from app.models.memory import MemoryManager
    mgr = MemoryManager(user_id)
    memory = mgr.load()
    if "user_preferences" in body:
        memory["user_preferences"] = body["user_preferences"]
    if "current_novel" in body:
        memory["current_novel"].update(body["current_novel"])
    mgr.save(memory)
    return {"status": "ok"}
