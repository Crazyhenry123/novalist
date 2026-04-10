import { useState, type FormEvent } from "react";
import type {
  NovelRequest,
  CharacterBrief,
  Genre,
  NarrativeStructure,
  WritingStyle,
  POV,
} from "../types";

interface Props {
  onSubmit: (req: NovelRequest) => void;
  disabled: boolean;
}

const GENRES: { value: Genre; label: string }[] = [
  { value: "xuanhuan", label: "玄幻" },
  { value: "xianxia", label: "仙侠" },
  { value: "wuxia", label: "武侠" },
  { value: "chuanyue", label: "穿越" },
  { value: "chongsheng", label: "重生" },
  { value: "dushi", label: "都市" },
  { value: "yanqing", label: "言情" },
  { value: "danmei", label: "耽美" },
  { value: "xitong", label: "系统/游戏" },
  { value: "gongdou", label: "宫斗/宅斗" },
  { value: "moshi", label: "末世" },
  { value: "junshi", label: "军事" },
  { value: "fantasy", label: "西式奇幻" },
  { value: "science_fiction", label: "科幻" },
  { value: "mystery", label: "悬疑推理" },
  { value: "thriller", label: "惊悚" },
  { value: "romance", label: "现代言情" },
  { value: "horror", label: "恐怖" },
  { value: "literary", label: "纯文学" },
  { value: "historical", label: "历史" },
  { value: "young_adult", label: "青春校园" },
];

const STRUCTURES: { value: NarrativeStructure; label: string }[] = [
  { value: "three_act", label: "三幕式" },
  { value: "heros_journey", label: "英雄之旅" },
  { value: "save_the_cat", label: "救猫咪节拍表" },
  { value: "kishotenketsu", label: "起承转合" },
  { value: "freytags_pyramid", label: "弗赖塔格金字塔" },
  { value: "shengji", label: "升级流" },
  { value: "shuangwen", label: "爽文节奏" },
  { value: "fucho", label: "伏笔回收" },
  { value: "qifu", label: "起伏流（虐后甜）" },
];

const STYLES: { value: WritingStyle; label: string }[] = [
  { value: "commercial", label: "商业流畅" },
  { value: "literary", label: "文学细腻" },
  { value: "shuangkuai", label: "爽快打脸" },
  { value: "xijie", label: "细腻情感" },
  { value: "qingsong", label: "轻松搞笑" },
  { value: "rexue", label: "热血燃文" },
  { value: "nuexin", label: "虐心催泪" },
  { value: "guyan", label: "古言雅韵" },
  { value: "zhichang", label: "职场真实" },
  { value: "minimalist", label: "极简克制" },
  { value: "ornate", label: "华丽辞藻" },
  { value: "dialogue_heavy", label: "对话驱动" },
  { value: "action_paced", label: "快节奏动作" },
  { value: "introspective", label: "内心独白" },
];

const POVS: { value: POV; label: string }[] = [
  { value: "first_person", label: "第一人称" },
  { value: "third_limited", label: "第三人称有限" },
  { value: "third_omniscient", label: "第三人称全知" },
];

export default function StorySetup({ onSubmit, disabled }: Props) {
  const [premise, setPremise] = useState("");
  const [genre, setGenre] = useState<Genre>("xuanhuan");
  const [structure, setStructure] = useState<NarrativeStructure>("three_act");
  const [style, setStyle] = useState<WritingStyle>("commercial");
  const [pov, setPov] = useState<POV>("third_limited");
  const [chapters, setChapters] = useState(12);
  const [characters, setCharacters] = useState<CharacterBrief[]>([
    { name: "", role: "主角", description: "", motivation: "" },
  ]);
  const [settingNotes, setSettingNotes] = useState("");
  const [themeNotes, setThemeNotes] = useState("");
  const [tone, setTone] = useState("引人入胜、沉浸感强");

  function addCharacter() {
    setCharacters((prev) => [
      ...prev,
      { name: "", role: "", description: "", motivation: "" },
    ]);
  }

  function updateCharacter(i: number, field: keyof CharacterBrief, val: string) {
    setCharacters((prev) =>
      prev.map((c, idx) => (idx === i ? { ...c, [field]: val } : c))
    );
  }

  function removeCharacter(i: number) {
    setCharacters((prev) => prev.filter((_, idx) => idx !== i));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      premise,
      genre,
      structure,
      style,
      pov,
      target_chapters: chapters,
      characters: characters.filter((c) => c.name.trim()),
      setting_notes: settingNotes,
      theme_notes: themeNotes,
      tone,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <h2 style={styles.heading}>创建新小说</h2>

      <label style={styles.label}>
        故事前提
        <textarea
          value={premise}
          onChange={(e) => setPremise(e.target.value)}
          placeholder="一个天赋平平的少年意外获得上古传承，在修仙界从最底层一步步崛起，揭开一个尘封万年的惊天秘密..."
          style={{ ...styles.input, minHeight: 80, resize: "vertical" }}
          required
        />
      </label>

      <div style={styles.row}>
        <label style={styles.label}>
          类型
          <select value={genre} onChange={(e) => setGenre(e.target.value as Genre)} style={styles.input}>
            {GENRES.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
          </select>
        </label>
        <label style={styles.label}>
          结构
          <select value={structure} onChange={(e) => setStructure(e.target.value as NarrativeStructure)} style={styles.input}>
            {STRUCTURES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
      </div>

      <div style={styles.row}>
        <label style={styles.label}>
          写作风格
          <select value={style} onChange={(e) => setStyle(e.target.value as WritingStyle)} style={styles.input}>
            {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <label style={styles.label}>
          叙事视角
          <select value={pov} onChange={(e) => setPov(e.target.value as POV)} style={styles.input}>
            {POVS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </label>
        <label style={styles.label}>
          章节数
          <input
            type="number"
            min={3}
            max={200}
            value={chapters}
            onChange={(e) => setChapters(Number(e.target.value))}
            style={styles.input}
          />
        </label>
      </div>

      <div style={styles.section}>
        <h3 style={styles.subheading}>角色设定</h3>
        {characters.map((c, i) => (
          <div key={i} style={styles.charRow}>
            <input placeholder="姓名" value={c.name} onChange={(e) => updateCharacter(i, "name", e.target.value)} style={styles.charInput} />
            <input placeholder="角色" value={c.role} onChange={(e) => updateCharacter(i, "role", e.target.value)} style={styles.charInput} />
            <input placeholder="描述" value={c.description} onChange={(e) => updateCharacter(i, "description", e.target.value)} style={{ ...styles.charInput, flex: 2 }} />
            <input placeholder="动机" value={c.motivation} onChange={(e) => updateCharacter(i, "motivation", e.target.value)} style={styles.charInput} />
            <button type="button" onClick={() => removeCharacter(i)} style={styles.removeBtn}>x</button>
          </div>
        ))}
        <button type="button" onClick={addCharacter} style={styles.addBtn}>+ 添加角色</button>
      </div>

      <label style={styles.label}>
        世界设定
        <textarea value={settingNotes} onChange={(e) => setSettingNotes(e.target.value)} placeholder="可选：描述故事世界的设定，如修炼体系、时代背景、地理环境等..." style={{ ...styles.input, minHeight: 60 }} />
      </label>

      <label style={styles.label}>
        主题方向
        <textarea value={themeNotes} onChange={(e) => setThemeNotes(e.target.value)} placeholder="可选：想要探索的主题，如逆袭、成长、复仇、守护、证道等..." style={{ ...styles.input, minHeight: 60 }} />
      </label>

      <label style={styles.label}>
        基调
        <input value={tone} onChange={(e) => setTone(e.target.value)} style={styles.input} />
      </label>

      <button type="submit" style={styles.submitBtn} disabled={disabled || !premise.trim()}>
        {disabled ? "生成中..." : "开始生成"}
      </button>
    </form>
  );
}

const styles: Record<string, React.CSSProperties> = {
  form: { display: "flex", flexDirection: "column", gap: 20 },
  heading: { fontSize: 28, color: "#c9a0dc", fontFamily: "'Georgia', serif" },
  subheading: { fontSize: 16, color: "#aaa", marginBottom: 8 },
  label: { display: "flex", flexDirection: "column", gap: 6, color: "#bbb", fontSize: 14 },
  input: {
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid #333",
    background: "#1a1a1a",
    color: "#e8e8e8",
    fontSize: 14,
    fontFamily: "inherit",
  },
  row: { display: "flex", gap: 16 },
  section: { display: "flex", flexDirection: "column", gap: 8 },
  charRow: { display: "flex", gap: 8, alignItems: "center" },
  charInput: {
    flex: 1,
    padding: "8px 12px",
    borderRadius: 6,
    border: "1px solid #333",
    background: "#1a1a1a",
    color: "#e8e8e8",
    fontSize: 13,
  },
  removeBtn: {
    padding: "4px 10px",
    borderRadius: 4,
    border: "1px solid #444",
    background: "transparent",
    color: "#888",
    cursor: "pointer",
  },
  addBtn: {
    padding: "8px 16px",
    borderRadius: 6,
    border: "1px dashed #444",
    background: "transparent",
    color: "#888",
    cursor: "pointer",
    alignSelf: "flex-start",
  },
  submitBtn: {
    padding: "14px 32px",
    borderRadius: 8,
    border: "none",
    background: "#7c3aed",
    color: "white",
    fontSize: 16,
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 8,
    alignSelf: "flex-start",
  },
};
