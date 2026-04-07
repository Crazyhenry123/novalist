from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Genre(str, Enum):
    FANTASY = "fantasy"
    SCIENCE_FICTION = "science_fiction"
    MYSTERY = "mystery"
    THRILLER = "thriller"
    ROMANCE = "romance"
    HORROR = "horror"
    LITERARY = "literary"
    HISTORICAL = "historical"
    YA = "young_adult"
    # 中国网络文学类型
    XUANHUAN = "xuanhuan"            # 玄幻
    XIANXIA = "xianxia"              # 仙侠
    CHUANYUE = "chuanyue"            # 穿越
    CHONGSHENG = "chongsheng"        # 重生
    DUSHI = "dushi"                   # 都市
    XITONG = "xitong"                # 系统文/游戏
    GONGDOU = "gongdou"              # 宫斗/宅斗
    MOSHI = "moshi"                   # 末世
    WUXIA = "wuxia"                   # 武侠
    YANQING = "yanqing"              # 言情
    DANMEI = "danmei"                # 耽美
    JUNSHI = "junshi"                # 军事


class NarrativeStructure(str, Enum):
    THREE_ACT = "three_act"
    HEROS_JOURNEY = "heros_journey"
    SAVE_THE_CAT = "save_the_cat"
    KISHŌTENKETSU = "kishotenketsu"
    FREYTAGS_PYRAMID = "freytags_pyramid"
    # 中国网文结构
    SHENGJI = "shengji"              # 升级流（逐步升级打怪）
    FUCHO = "fucho"                  # 伏笔回收（层层伏笔、环环相扣）
    SHUANGWEN = "shuangwen"          # 爽文节奏（快速打脸、高潮迭起）
    QIFU = "qifu"                    # 起伏流（大起大落、虐后甜）


class WritingStyle(str, Enum):
    LITERARY = "literary"
    COMMERCIAL = "commercial"
    MINIMALIST = "minimalist"
    ORNATE = "ornate"
    DIALOGUE_HEAVY = "dialogue_heavy"
    ACTION_PACED = "action_paced"
    INTROSPECTIVE = "introspective"
    # 中国网文风格
    SHUANGKUAI = "shuangkuai"       # 爽快流（节奏快、打脸爽）
    XIJIE = "xijie"                  # 细腻流（情感细腻、心理描写）
    QINGSONG = "qingsong"            # 轻松搞笑（幽默吐槽、段子频出）
    REXUE = "rexue"                  # 热血燃文（激情澎湃、斗志昂扬）
    NUEXIN = "nuexin"               # 虐心流（虐恋、催泪、刀子）
    GUYAN = "guyan"                  # 古言风（古典雅致、诗词穿插）
    ZHICHANG = "zhichang"            # 职场风（专业术语、行业真实感）


class POV(str, Enum):
    FIRST_PERSON = "first_person"
    THIRD_LIMITED = "third_limited"
    THIRD_OMNISCIENT = "third_omniscient"


class CharacterBrief(BaseModel):
    name: str
    role: str = Field(description="主角、反派、师父、盟友等")
    description: str = ""
    motivation: str = ""


class NovelRequest(BaseModel):
    premise: str = Field(description="核心故事创意或简介")
    genre: Genre = Genre.XUANHUAN
    structure: NarrativeStructure = NarrativeStructure.THREE_ACT
    style: WritingStyle = WritingStyle.COMMERCIAL
    pov: POV = POV.THIRD_LIMITED
    target_chapters: int = Field(default=12, ge=3, le=50)
    characters: list[CharacterBrief] = Field(default_factory=list)
    setting_notes: str = ""
    theme_notes: str = ""
    tone: str = "引人入胜、沉浸感强"


class StoryStructure(BaseModel):
    title: str = ""
    theme_statement: str = ""
    act_breakdown: list[str] = Field(default_factory=list)
    chapter_plan: list[str] = Field(default_factory=list)
    turning_points: list[str] = Field(default_factory=list)


class CharacterProfile(BaseModel):
    name: str
    role: str
    backstory: str = ""
    motivation: str = ""
    arc: str = ""
    voice_notes: str = ""
    relationships: dict[str, str] = Field(default_factory=dict)


class WorldDetail(BaseModel):
    setting_description: str = ""
    time_period: str = ""
    locations: list[str] = Field(default_factory=list)
    rules_and_systems: str = ""
    atmosphere: str = ""
    cultural_notes: str = ""


class PlotOutline(BaseModel):
    beats: list[str] = Field(default_factory=list)
    scene_outline: list[str] = Field(default_factory=list)
    subplots: list[str] = Field(default_factory=list)
    foreshadowing: list[str] = Field(default_factory=list)


class ChapterDraft(BaseModel):
    chapter_num: int
    title: str = ""
    content: str = ""
    word_count: int = 0
    pov_character: str = ""
    summary: str = ""


class StreamMessage(BaseModel):
    type: str
    agent: str = ""
    content: str = ""
    data: Optional[dict] = None
    chapter: Optional[int] = None
    word_count: Optional[int] = None
