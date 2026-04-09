"""DynamoDB for index, S3 for content — CRUD operations for novels."""

import time
import uuid
import boto3
import logging
from boto3.dynamodb.conditions import Key

from app.config import settings
from app.models.s3_store import S3Store

logger = logging.getLogger(__name__)


class NovelStore:
    def __init__(self):
        ddb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self.novels = ddb.Table(settings.novels_table)
        self.s3 = S3Store()

    def _s3_prefix(self, user_id: str, novel_id: str) -> str:
        return f"users/{user_id}/novels/{novel_id}"

    def create_novel(self, user_id: str, novel_id: str = "", **kwargs) -> str:
        if not novel_id:
            novel_id = str(uuid.uuid4())
        now = int(time.time())
        item = {
            "user_id": user_id,
            "novel_id": novel_id,
            "status": kwargs.get("status", "step1_draft"),
            "premise": (kwargs.get("premise", ""))[:200],
            "created_at": now,
            "updated_at": now,
        }
        if kwargs.get("title"):
            item["title"] = kwargs["title"]
        self.novels.put_item(Item=item)
        return novel_id

    def update_status(self, user_id: str, novel_id: str, status: str):
        self.novels.update_item(
            Key={"user_id": user_id, "novel_id": novel_id},
            UpdateExpression="SET #s = :s, updated_at = :t",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status, ":t": int(time.time())},
        )

    def list_novels(self, user_id: str) -> list:
        resp = self.novels.query(KeyConditionExpression=Key("user_id").eq(user_id))
        return resp.get("Items", [])

    def get_novel_meta(self, user_id: str, novel_id: str) -> dict:
        resp = self.novels.get_item(Key={"user_id": user_id, "novel_id": novel_id})
        return resp.get("Item", {})

    # ── S3 content operations ──

    def save_step1(self, user_id: str, novel_id: str, structure: str, characters: str, world: str):
        prefix = self._s3_prefix(user_id, novel_id)
        self.s3.save_text(f"{prefix}/step1/structure.md", structure)
        self.s3.save_text(f"{prefix}/step1/characters.md", characters)
        self.s3.save_text(f"{prefix}/step1/world.md", world)
        self.update_status(user_id, novel_id, "step1_done")

    def load_step1(self, user_id: str, novel_id: str) -> dict:
        prefix = self._s3_prefix(user_id, novel_id)
        return {
            "structure": self.s3.load_text(f"{prefix}/step1/structure.md"),
            "characters": self.s3.load_text(f"{prefix}/step1/characters.md"),
            "world": self.s3.load_text(f"{prefix}/step1/world.md"),
        }

    def save_step2(self, user_id: str, novel_id: str, plot: str):
        prefix = self._s3_prefix(user_id, novel_id)
        self.s3.save_text(f"{prefix}/step2/plot.md", plot)
        self.update_status(user_id, novel_id, "step2_done")

    def load_step2(self, user_id: str, novel_id: str) -> dict:
        prefix = self._s3_prefix(user_id, novel_id)
        return {"plot": self.s3.load_text(f"{prefix}/step2/plot.md")}

    def save_chapter(self, user_id: str, novel_id: str, chapter_num: int, content: str):
        prefix = self._s3_prefix(user_id, novel_id)
        self.s3.save_text(f"{prefix}/chapters/{chapter_num:02d}.md", content)
        self.update_status(user_id, novel_id, "writing")

    def load_chapters(self, user_id: str, novel_id: str) -> dict[int, str]:
        """Returns {chapter_num: content}"""
        prefix = self._s3_prefix(user_id, novel_id)
        keys = self.s3.list_keys(f"{prefix}/chapters/")
        chapters = {}
        for key in keys:
            filename = key.split("/")[-1]
            if filename.endswith(".md"):
                num = int(filename.replace(".md", ""))
                chapters[num] = self.s3.load_text(key)
        return chapters

    def get_novel_full(self, user_id: str, novel_id: str) -> dict:
        """Load complete novel: meta + all S3 content."""
        meta = self.get_novel_meta(user_id, novel_id)
        if not meta:
            return {}
        step1 = self.load_step1(user_id, novel_id)
        step2 = self.load_step2(user_id, novel_id)
        chapters = self.load_chapters(user_id, novel_id)
        return {**meta, **step1, **step2, "chapters": chapters}
