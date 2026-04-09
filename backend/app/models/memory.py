import re
import time
import json
import logging
from app.models.s3_store import S3Store

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, user_id: str):
        self.store = S3Store()
        self.user_id = user_id
        self.key = f"users/{user_id}/memory.json"

    def load(self) -> dict:
        return self.store.load_json(self.key) or {
            "user_preferences": {},
            "current_novel": {},
            "chat_history_summary": "",
            "updated_at": 0
        }

    def save(self, memory: dict):
        memory["updated_at"] = int(time.time())
        self.store.save_json(self.key, memory)

    def update_after_step(self, novel_id: str, step: int, outputs: dict):
        """Extract key facts from step output and update memory."""
        memory = self.load()
        novel_ctx = memory.get("current_novel", {})
        novel_ctx["novel_id"] = novel_id

        if step == 1:
            # Extract title from structure if present
            structure = outputs.get("structure", "")
            for line in structure.split("\n"):
                if "\u3010\u6807\u9898\u3011" in line:
                    novel_ctx["title"] = line.replace("\u3010\u6807\u9898\u3011", "").strip()
                    break
            # Extract character names
            characters = outputs.get("characters", "")
            names = []
            for line in characters.split("\n"):
                if "\u3010\u89d2\u8272\u540d\u3011" in line:
                    name = line.replace("\u3010\u89d2\u8272\u540d\u3011", "").strip()
                    if name:
                        names.append(name)
            if names:
                novel_ctx["key_characters"] = names
            # Store world rules summary (first 500 chars)
            world = outputs.get("world", "")
            if world:
                novel_ctx["world_summary"] = world[:500]

        elif step == 2:
            plot = outputs.get("plot", "")
            # Extract chapter count
            chapter_nums = re.findall(r"\u7b2c(\d+)\u7ae0", plot)
            if chapter_nums:
                novel_ctx["total_chapters"] = max(int(n) for n in chapter_nums)
            # Store plot summary (first 500 chars)
            if plot:
                novel_ctx["plot_summary"] = plot[:500]

        elif step == 3:
            chapter_num = outputs.get("chapter_num", 0)
            written = novel_ctx.get("chapters_written", [])
            if chapter_num not in written:
                written.append(chapter_num)
            novel_ctx["chapters_written"] = sorted(written)

        memory["current_novel"] = novel_ctx
        self.save(memory)

    def format_context(self) -> str:
        """Format memory as context string to prepend to agent prompts."""
        memory = self.load()
        parts = []

        novel = memory.get("current_novel", {})
        if novel:
            parts.append("\u3010\u5f53\u524d\u521b\u4f5c\u4e0a\u4e0b\u6587\u3011")
            if novel.get("title"):
                parts.append(f"\u4f5c\u54c1\u540d\u79f0\uff1a{novel['title']}")
            if novel.get("key_characters"):
                parts.append(f"\u6838\u5fc3\u89d2\u8272\uff1a{'\u3001'.join(novel['key_characters'])}")
            if novel.get("world_summary"):
                parts.append(f"\u4e16\u754c\u89c2\u6982\u8981\uff1a{novel['world_summary'][:200]}")
            if novel.get("plot_summary"):
                parts.append(f"\u60c5\u8282\u6982\u8981\uff1a{novel['plot_summary'][:200]}")
            if novel.get("chapters_written"):
                parts.append(f"\u5df2\u5b8c\u6210\u7ae0\u8282\uff1a{novel['chapters_written']}")

        prefs = memory.get("user_preferences", {})
        if prefs:
            if prefs.get("notes"):
                parts.append(f"\u4f5c\u8005\u504f\u597d\uff1a{prefs['notes']}")

        if not parts:
            return ""
        return "\n".join(parts) + "\n\n"
