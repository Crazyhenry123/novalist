import re
import time
import json
import logging
from app.models.s3_store import S3Store

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, user_id: str, novel_id: str):
        self.store = S3Store()
        self.user_id = user_id
        self.novel_id = novel_id
        self.key = f"users/{user_id}/novels/{novel_id}/memory.json"

    def load(self) -> dict:
        return self.store.load_json(self.key) or {
            "user_preferences": {},
            "current_novel": {},
            "chapter_summaries": {},
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
                if "【标题】" in line:
                    novel_ctx["title"] = line.replace("【标题】", "").strip()
                    break

            # Extract ALL character names with roles
            characters = outputs.get("characters", "")
            char_list = []
            current_name = ""
            current_role = ""
            for line in characters.split("\n"):
                if "【角色名】" in line:
                    if current_name:
                        char_list.append({"name": current_name, "role": current_role})
                    current_name = line.replace("【角色名】", "").strip()
                    current_role = ""
                elif "【角色定位】" in line or "【身份】" in line:
                    current_role = line.split("】", 1)[-1].strip() if "】" in line else ""
                elif "【职业】" in line and not current_role:
                    current_role = line.split("】", 1)[-1].strip() if "】" in line else ""
            if current_name:
                char_list.append({"name": current_name, "role": current_role})

            if char_list:
                novel_ctx["characters_detail"] = char_list
                novel_ctx["key_characters"] = [c["name"] for c in char_list]

            # Store world rules summary (first 1000 chars)
            world = outputs.get("world", "")
            if world:
                novel_ctx["world_summary"] = world[:1000]

            # Store structure summary (first 1000 chars)
            if structure:
                novel_ctx["structure_summary"] = structure[:1000]

        elif step == 2:
            plot = outputs.get("plot", "")
            # Extract chapter count and titles
            chapter_nums = re.findall(r"第(\d+)章", plot)
            if chapter_nums:
                novel_ctx["total_chapters"] = max(int(n) for n in chapter_nums)

            # Extract chapter titles
            chapter_titles = {}
            for match in re.finditer(r"第(\d+)章[：:\s]*(.+?)(?:\n|$)", plot):
                num = int(match.group(1))
                title = match.group(2).strip()
                chapter_titles[str(num)] = title
            if chapter_titles:
                novel_ctx["chapter_titles"] = chapter_titles

            # Extract key plot points (lines containing keywords)
            plot_points = []
            for line in plot.split("\n"):
                line = line.strip()
                if any(kw in line for kw in ["转折", "冲突", "高潮", "危机", "揭示", "真相", "决战", "关键"]):
                    if line and len(line) < 200:
                        plot_points.append(line)
            if plot_points:
                novel_ctx["key_plot_points"] = plot_points[:20]

            # Extract subplots
            subplots = []
            for line in plot.split("\n"):
                line = line.strip()
                if any(kw in line for kw in ["支线", "副线", "暗线", "伏笔"]):
                    if line and len(line) < 200:
                        subplots.append(line)
            if subplots:
                novel_ctx["subplots"] = subplots[:10]

            # Store full plot summary (first 2000 chars)
            if plot:
                novel_ctx["plot_summary"] = plot[:2000]

        elif step == 3:
            chapter_num = outputs.get("chapter_num", 0)
            written = novel_ctx.get("chapters_written", [])
            if chapter_num not in written:
                written.append(chapter_num)
            novel_ctx["chapters_written"] = sorted(written)

            # Store chapter content summary for continuity
            chapter_content = outputs.get("chapter_content", "")
            if chapter_content:
                chapter_summaries = memory.get("chapter_summaries", {})
                # Store first 800 chars as summary, plus extract key scenes
                summary_parts = []
                summary_parts.append(chapter_content[:800])

                # Extract key scenes (paragraphs with dialogue or action)
                key_scenes = []
                paragraphs = chapter_content.split("\n\n")
                for para in paragraphs:
                    para = para.strip()
                    if len(para) > 50 and any(kw in para for kw in ["「", "」", """, """, "说道", "喊道", "叫道", "低声"]):
                        key_scenes.append(para[:200])
                        if len(key_scenes) >= 3:
                            break

                chapter_summaries[str(chapter_num)] = {
                    "summary": summary_parts[0] if summary_parts else "",
                    "key_scenes": key_scenes,
                }
                memory["chapter_summaries"] = chapter_summaries

        memory["current_novel"] = novel_ctx
        self.save(memory)

    def format_context(self) -> str:
        """Format memory as context string to prepend to agent prompts."""
        memory = self.load()
        parts = []

        novel = memory.get("current_novel", {})
        if novel:
            parts.append("【当前创作上下文】")
            if novel.get("title"):
                parts.append(f"作品名称：{novel['title']}")

            if novel.get("characters_detail"):
                chars_str = "、".join(
                    f"{c['name']}（{c['role']}）" if c.get("role") else c["name"]
                    for c in novel["characters_detail"]
                )
                parts.append(f"角色列表：{chars_str}")
            elif novel.get("key_characters"):
                parts.append(f"核心角色：{'、'.join(novel['key_characters'])}")

            if novel.get("structure_summary"):
                parts.append(f"故事结构：{novel['structure_summary'][:300]}")
            if novel.get("world_summary"):
                parts.append(f"世界观概要：{novel['world_summary'][:300]}")
            if novel.get("plot_summary"):
                parts.append(f"情节概要：{novel['plot_summary'][:500]}")

            if novel.get("chapter_titles"):
                titles_str = "、".join(
                    f"第{k}章：{v}" for k, v in sorted(
                        novel["chapter_titles"].items(), key=lambda x: int(x[0])
                    )
                )
                parts.append(f"章节标题：{titles_str}")

            if novel.get("key_plot_points"):
                parts.append("关键情节点：" + "；".join(novel["key_plot_points"][:10]))

            if novel.get("subplots"):
                parts.append("支线情节：" + "；".join(novel["subplots"][:5]))

            if novel.get("chapters_written"):
                parts.append(f"已完成章节：{novel['chapters_written']}")

        # Include chapter summaries for continuity
        chapter_summaries = memory.get("chapter_summaries", {})
        if chapter_summaries:
            parts.append("\n【已完成章节摘要】")
            for num in sorted(chapter_summaries.keys(), key=lambda x: int(x)):
                ch_info = chapter_summaries[num]
                parts.append(f"\n第{num}章摘要：")
                if ch_info.get("summary"):
                    parts.append(ch_info["summary"][:400])
                if ch_info.get("key_scenes"):
                    parts.append("关键场景：")
                    for scene in ch_info["key_scenes"][:2]:
                        parts.append(f"  - {scene[:150]}")

        prefs = memory.get("user_preferences", {})
        if prefs:
            if prefs.get("notes"):
                parts.append(f"作者偏好：{prefs['notes']}")

        if not parts:
            return ""
        return "\n".join(parts) + "\n\n"
