"""Tests for Pydantic models in app.models.schemas."""

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    Genre,
    NarrativeStructure,
    WritingStyle,
    POV,
    CharacterBrief,
    NovelRequest,
    StoryStructure,
    CharacterProfile,
    WorldDetail,
    PlotOutline,
    ChapterDraft,
    StreamMessage,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestGenreEnum:
    def test_all_values(self):
        expected = {
            "fantasy", "science_fiction", "mystery", "thriller",
            "romance", "horror", "literary", "historical", "young_adult",
            # Chinese web novel genres
            "xuanhuan", "xianxia", "chuanyue", "chongsheng", "dushi",
            "xitong", "gongdou", "moshi", "wuxia", "yanqing", "danmei", "junshi",
        }
        assert {g.value for g in Genre} == expected

    def test_from_value(self):
        assert Genre("fantasy") is Genre.FANTASY
        assert Genre("science_fiction") is Genre.SCIENCE_FICTION

    def test_chinese_genre_xuanhuan(self):
        assert Genre("xuanhuan") is Genre.XUANHUAN

    def test_chinese_genre_xianxia(self):
        assert Genre("xianxia") is Genre.XIANXIA

    def test_chinese_genre_chuanyue(self):
        assert Genre("chuanyue") is Genre.CHUANYUE

    def test_chinese_genre_chongsheng(self):
        assert Genre("chongsheng") is Genre.CHONGSHENG

    def test_chinese_genre_dushi(self):
        assert Genre("dushi") is Genre.DUSHI

    def test_chinese_genre_xitong(self):
        assert Genre("xitong") is Genre.XITONG

    def test_chinese_genre_gongdou(self):
        assert Genre("gongdou") is Genre.GONGDOU

    def test_chinese_genre_moshi(self):
        assert Genre("moshi") is Genre.MOSHI

    def test_chinese_genre_wuxia(self):
        assert Genre("wuxia") is Genre.WUXIA

    def test_chinese_genre_yanqing(self):
        assert Genre("yanqing") is Genre.YANQING

    def test_chinese_genre_danmei(self):
        assert Genre("danmei") is Genre.DANMEI

    def test_chinese_genre_junshi(self):
        assert Genre("junshi") is Genre.JUNSHI


class TestNarrativeStructureEnum:
    def test_all_values(self):
        expected = {
            "three_act", "heros_journey", "save_the_cat",
            "kishotenketsu", "freytags_pyramid",
            # Chinese web novel structures
            "shengji", "fucho", "shuangwen", "qifu",
        }
        assert {n.value for n in NarrativeStructure} == expected

    def test_chinese_structure_shengji(self):
        assert NarrativeStructure("shengji") is NarrativeStructure.SHENGJI

    def test_chinese_structure_fucho(self):
        assert NarrativeStructure("fucho") is NarrativeStructure.FUCHO

    def test_chinese_structure_shuangwen(self):
        assert NarrativeStructure("shuangwen") is NarrativeStructure.SHUANGWEN

    def test_chinese_structure_qifu(self):
        assert NarrativeStructure("qifu") is NarrativeStructure.QIFU


class TestWritingStyleEnum:
    def test_all_values(self):
        expected = {
            "literary", "commercial", "minimalist", "ornate",
            "dialogue_heavy", "action_paced", "introspective",
            # Chinese web novel styles
            "shuangkuai", "xijie", "qingsong", "rexue",
            "nuexin", "guyan", "zhichang",
        }
        assert {w.value for w in WritingStyle} == expected

    def test_chinese_style_shuangkuai(self):
        assert WritingStyle("shuangkuai") is WritingStyle.SHUANGKUAI

    def test_chinese_style_xijie(self):
        assert WritingStyle("xijie") is WritingStyle.XIJIE

    def test_chinese_style_qingsong(self):
        assert WritingStyle("qingsong") is WritingStyle.QINGSONG

    def test_chinese_style_rexue(self):
        assert WritingStyle("rexue") is WritingStyle.REXUE

    def test_chinese_style_nuexin(self):
        assert WritingStyle("nuexin") is WritingStyle.NUEXIN

    def test_chinese_style_guyan(self):
        assert WritingStyle("guyan") is WritingStyle.GUYAN

    def test_chinese_style_zhichang(self):
        assert WritingStyle("zhichang") is WritingStyle.ZHICHANG


class TestPOVEnum:
    def test_all_values(self):
        expected = {"first_person", "third_limited", "third_omniscient"}
        assert {p.value for p in POV} == expected


# ---------------------------------------------------------------------------
# CharacterBrief
# ---------------------------------------------------------------------------

class TestCharacterBrief:
    def test_minimal(self):
        cb = CharacterBrief(name="Alice", role="protagonist")
        assert cb.name == "Alice"
        assert cb.role == "protagonist"
        assert cb.description == ""
        assert cb.motivation == ""

    def test_full(self):
        cb = CharacterBrief(
            name="Bob", role="antagonist",
            description="Tall and menacing", motivation="Power",
        )
        assert cb.description == "Tall and menacing"
        assert cb.motivation == "Power"


# ---------------------------------------------------------------------------
# NovelRequest
# ---------------------------------------------------------------------------

class TestNovelRequest:
    def test_defaults(self):
        nr = NovelRequest(premise="A wizard finds a cat")
        # Default genre changed to XUANHUAN
        assert nr.genre is Genre.XUANHUAN
        assert nr.structure is NarrativeStructure.THREE_ACT
        assert nr.style is WritingStyle.COMMERCIAL
        assert nr.pov is POV.THIRD_LIMITED
        assert nr.target_chapters == 12
        assert nr.characters == []
        assert nr.setting_notes == ""
        assert nr.theme_notes == ""
        # Default tone is now Chinese
        assert nr.tone == "引人入胜、沉浸感强"

    def test_custom_values(self):
        nr = NovelRequest(
            premise="Space opera",
            genre=Genre.SCIENCE_FICTION,
            structure=NarrativeStructure.HEROS_JOURNEY,
            style=WritingStyle.ACTION_PACED,
            pov=POV.FIRST_PERSON,
            target_chapters=20,
            setting_notes="Mars colony",
            theme_notes="Identity",
            tone="epic",
        )
        assert nr.genre is Genre.SCIENCE_FICTION
        assert nr.target_chapters == 20

    def test_chinese_params(self):
        nr = NovelRequest(
            premise="穿越到古代",
            genre=Genre.CHUANYUE,
            structure=NarrativeStructure.SHUANGWEN,
            style=WritingStyle.SHUANGKUAI,
        )
        assert nr.genre is Genre.CHUANYUE
        assert nr.structure is NarrativeStructure.SHUANGWEN
        assert nr.style is WritingStyle.SHUANGKUAI

    def test_target_chapters_min(self):
        nr = NovelRequest(premise="x", target_chapters=3)
        assert nr.target_chapters == 3

    def test_target_chapters_max(self):
        nr = NovelRequest(premise="x", target_chapters=50)
        assert nr.target_chapters == 50

    def test_target_chapters_below_min_raises(self):
        with pytest.raises(ValidationError):
            NovelRequest(premise="x", target_chapters=2)

    def test_target_chapters_above_max_raises(self):
        with pytest.raises(ValidationError):
            NovelRequest(premise="x", target_chapters=51)

    def test_with_characters(self):
        nr = NovelRequest(
            premise="y",
            characters=[
                CharacterBrief(name="A", role="protagonist"),
                CharacterBrief(name="B", role="antagonist"),
            ],
        )
        assert len(nr.characters) == 2


# ---------------------------------------------------------------------------
# Other models -- basic construction
# ---------------------------------------------------------------------------

class TestStoryStructure:
    def test_defaults(self):
        ss = StoryStructure()
        assert ss.title == ""
        assert ss.act_breakdown == []

    def test_full(self):
        ss = StoryStructure(
            title="My Novel",
            theme_statement="Love conquers all",
            act_breakdown=["Act 1", "Act 2", "Act 3"],
            chapter_plan=["Ch1 intro"],
            turning_points=["Midpoint twist"],
        )
        assert ss.title == "My Novel"
        assert len(ss.act_breakdown) == 3


class TestCharacterProfile:
    def test_minimal(self):
        cp = CharacterProfile(name="Eve", role="mentor")
        assert cp.name == "Eve"
        assert cp.relationships == {}

    def test_with_relationships(self):
        cp = CharacterProfile(
            name="Eve", role="mentor",
            relationships={"Adam": "student"},
        )
        assert cp.relationships["Adam"] == "student"


class TestWorldDetail:
    def test_defaults(self):
        wd = WorldDetail()
        assert wd.locations == []
        assert wd.setting_description == ""


class TestPlotOutline:
    def test_defaults(self):
        po = PlotOutline()
        assert po.beats == []
        assert po.subplots == []


class TestChapterDraft:
    def test_construction(self):
        cd = ChapterDraft(chapter_num=1, title="Chapter One", content="Once upon a time")
        assert cd.chapter_num == 1
        assert cd.word_count == 0  # default, not auto-calculated


class TestStreamMessage:
    def test_minimal(self):
        sm = StreamMessage(type="info")
        assert sm.type == "info"
        assert sm.data is None
        assert sm.chapter is None

    def test_full(self):
        sm = StreamMessage(
            type="agent_result", agent="editor",
            content="Done", data={"k": "v"}, chapter=3, word_count=5000,
        )
        assert sm.chapter == 3
        assert sm.word_count == 5000
