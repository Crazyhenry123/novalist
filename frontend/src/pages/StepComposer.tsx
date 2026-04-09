import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import StepProgress from "../components/StepProgress";
import StorySetup from "../components/StorySetup";
import ResultEditor from "../components/ResultEditor";
import ChapterList from "../components/ChapterList";
import RefineChat from "../components/RefineChat";
import { useSSE } from "../hooks/useSSE";
import { useNovel } from "../hooks/useNovel";
import { useAuth } from "../auth/CognitoProvider";
import type { NovelRequest } from "../types";

interface Props {
  novelId: string;
  onBack: () => void;
}

export default function StepComposer({ novelId, onBack }: Props) {
  const { idToken } = useAuth();
  const { loadNovel, saveStep1, saveStep2, refreshNovel, userId } = useNovel();
  const { messages, generating, generate, cancel, clearMessages } = useSSE();

  const [step, setStep] = useState(1);
  const [currentNovelId, setCurrentNovelId] = useState(novelId);

  // Step 1 results — one per agent tab
  const [structureText, setStructureText] = useState("");
  const [charactersText, setCharactersText] = useState("");
  const [worldText, setWorldText] = useState("");

  // Streaming buffers per agent (accumulate text_chunk events)
  const streamBuf = useRef<Record<string, string>>({
    story_architect: "",
    character_developer: "",
    world_builder: "",
    plot_weaver: "",
    prose_writer: "",
    editor: "",
    chat: "",
  });

  // Step 2 results
  const [plotText, setPlotText] = useState("");
  const [parsedAbstracts, setParsedAbstracts] = useState<Array<{ num: number; title: string; abstract: string }>>([]);
  const [expandedAbstract, setExpandedAbstract] = useState<number | null>(null);

  // Step 3 state
  const [chapters, setChapters] = useState<
    Array<{ num: number; outline: string; status: "pending" | "generating" | "done"; content?: string }>
  >([]);
  const [generatingChapter, setGeneratingChapter] = useState<number | null>(null);

  const lastProcessedRef = useRef(0);

  // Load existing novel
  useEffect(() => {
    if (novelId) {
      loadNovel(novelId).then((novel) => {
        if (novel) {
          setCurrentNovelId(novel.novel_id);
          if (novel.structure) setStructureText(novel.structure);
          if (novel.characters) setCharactersText(novel.characters);
          if (novel.world) setWorldText(novel.world);
          if (novel.plot) setPlotText(novel.plot);

          // Load chapters from novel state if available
          if (novel.chapters && typeof novel.chapters === "object") {
            setChapters(prev => prev.map(ch => {
              const loaded = novel.chapters?.[ch.num];
              return loaded ? { ...ch, status: "done" as const, content: loaded } : ch;
            }));
          }

          if (novel.status === "step1_done" || novel.status === "step2_draft") {
            setStep(2);
          } else if (novel.status === "step2_done" || novel.status === "writing" || novel.status === "completed") {
            setStep(3);
            if (novel.plot) parseChaptersFromPlot(novel.plot, novel.chapters);
          }
        }
      });
    }
  }, [novelId, loadNovel]);

  function parsePlotToAbstracts(plot: string): Array<{ num: number; title: string; abstract: string }> {
    const items: Array<{ num: number; title: string; abstract: string }> = [];
    // Split by chapter headings: 第X章：...
    const parts = plot.split(/(?=第\s*\d+\s*章[：:：]?)/);
    for (const part of parts) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      const headMatch = trimmed.match(/^第\s*(\d+)\s*章[：:：]?\s*(.*)/s);
      if (headMatch) {
        const num = parseInt(headMatch[1], 10);
        const rest = headMatch[2].trim();
        // First line is the title, rest is the abstract
        const lines = rest.split("\n");
        const title = lines[0]?.trim() || `第${num}章`;
        const abstract = lines.slice(1).join("\n").trim();
        items.push({ num, title, abstract });
      }
    }
    return items;
  }

  function parseChaptersFromPlot(plot: string, existingChapters?: Record<number, string>) {
    const lines = plot.split("\n").filter((l) => l.trim());
    const items: typeof chapters = [];
    let num = 0;

    for (const line of lines) {
      const match = line.match(/^(?:第\s*(\d+)\s*章|(\d+)[.、)\s])/);
      if (match) {
        num = parseInt(match[1] || match[2], 10);
        const outline = line.replace(/^(?:第\s*\d+\s*章[：:\s]*|\d+[.、)\s]*)/, "").trim();
        const has = existingChapters && existingChapters[num];
        items.push({ num, outline: outline || `第${num}章`, status: has ? "done" : "pending", content: has ? existingChapters[num] : undefined });
      }
    }

    if (items.length === 0) {
      lines.forEach((line, i) => {
        if (line.trim()) {
          const n = i + 1;
          const has = existingChapters && existingChapters[n];
          items.push({ num: n, outline: line.trim(), status: has ? "done" : "pending", content: has ? existingChapters[n] : undefined });
        }
      });
    }

    setChapters(items);
  }

  // Parse abstracts when plotText changes and not generating
  useEffect(() => {
    if (plotText && !generating && step === 2) {
      const abstracts = parsePlotToAbstracts(plotText);
      if (abstracts.length > 0) {
        setParsedAbstracts(abstracts);
      }
    }
  }, [plotText, generating, step]);

  // ── Process SSE messages ───────────────────────────────────
  useEffect(() => {
    for (let i = lastProcessedRef.current; i < messages.length; i++) {
      const msg = messages[i];

      // Capture novel_id from pipeline_start
      if (msg.type === "pipeline_start" && msg.novel_id) {
        setCurrentNovelId(msg.novel_id);
      }

      // Text chunks — route to correct buffer by agent name
      if (msg.type === "text_chunk" && msg.agent && msg.content) {
        const agent = msg.agent;
        streamBuf.current[agent] = (streamBuf.current[agent] || "") + msg.content;

        if (step === 1) {
          if (agent === "story_architect") setStructureText(streamBuf.current[agent]);
          else if (agent === "character_developer") setCharactersText(streamBuf.current[agent]);
          else if (agent === "world_builder") setWorldText(streamBuf.current[agent]);
        } else if (step === 2) {
          if (agent === "plot_weaver") setPlotText(streamBuf.current[agent]);
        } else if (step === 3 && generatingChapter !== null) {
          const content = (streamBuf.current["prose_writer"] || "") + (streamBuf.current["editor"] || "");
          setChapters((prev) =>
            prev.map((ch) => ch.num === generatingChapter ? { ...ch, status: "generating", content } : ch)
          );
        }
      }

      // Agent complete — prefer streamed buffer over agent_complete data
      if (msg.type === "agent_complete" && msg.agent && msg.data) {
        const agent = msg.agent;
        const fullText = (msg.data.full_text as string) || (msg.data.preview as string) || "";
        if (step === 1) {
          // Only use agent_complete data if we don't already have streamed content
          if (agent === "story_architect" && fullText && !streamBuf.current.story_architect)
            setStructureText(fullText);
          else if (agent === "character_developer" && fullText && !streamBuf.current.character_developer)
            setCharactersText(fullText);
          else if (agent === "world_builder" && fullText && !streamBuf.current.world_builder)
            setWorldText(fullText);
        } else if (step === 2 && agent === "plot_weaver" && fullText && !streamBuf.current.plot_weaver) {
          setPlotText(fullText);
        }
      }

      // Step complete
      if (msg.type === "step_complete") {
        // Results already set via agent_complete events
      }

      // Chapter done
      if (msg.type === "step_complete" && step === 3 && generatingChapter !== null) {
        const content = (streamBuf.current["prose_writer"] || "") + (streamBuf.current["editor"] || "");
        setChapters((prev) =>
          prev.map((ch) => ch.num === generatingChapter ? { ...ch, status: "done", content } : ch)
        );
        setGeneratingChapter(null);
      }

      // Done event
      if (msg.type === "done") {
        if (step === 3 && generatingChapter !== null) {
          const content = streamBuf.current["prose_writer"] || streamBuf.current["editor"] || "";
          if (content) {
            setChapters((prev) =>
              prev.map((ch) => ch.num === generatingChapter ? { ...ch, status: "done", content } : ch)
            );
          }
          setGeneratingChapter(null);
        }
      }

      // Error
      if (msg.type === "error") {
        if (step === 3 && generatingChapter !== null) {
          setChapters((prev) =>
            prev.map((ch) => ch.num === generatingChapter ? { ...ch, status: "pending" } : ch)
          );
          setGeneratingChapter(null);
        }
      }
    }

    lastProcessedRef.current = messages.length;
  }, [messages, step, generatingChapter]);

  // ── Step handlers ──────────────────────────────────────────

  const handleStep1Generate = useCallback(
    (req: NovelRequest) => {
      setStructureText("");
      setCharactersText("");
      setWorldText("");
      streamBuf.current = { story_architect: "", character_developer: "", world_builder: "", plot_weaver: "", prose_writer: "", editor: "", chat: "" };
      lastProcessedRef.current = 0;
      clearMessages();

      const body: Record<string, unknown> = { ...req, user_id: userId };
      if (currentNovelId) body.novel_id = currentNovelId;

      generate("/api/step1", body, idToken);
    },
    [userId, currentNovelId, idToken, generate, clearMessages]
  );

  const handleStep1Confirm = useCallback(async () => {
    if (!currentNovelId) return;
    try {
      await saveStep1(currentNovelId, {
        structure: structureText,
        characters: charactersText,
        world: worldText,
      });
      setStep(2);
      clearMessages();
      lastProcessedRef.current = 0;
    } catch (err) {
      alert("保存失败，请重试");
    }
  }, [currentNovelId, structureText, charactersText, worldText, saveStep1, clearMessages]);

  const handleStep2Generate = useCallback(() => {
    setPlotText("");
    streamBuf.current.plot_weaver = "";
    lastProcessedRef.current = 0;
    clearMessages();

    generate("/api/step2", {
      novel_id: currentNovelId,
      structure: structureText,
      characters: charactersText,
      world: worldText,
      user_id: userId,
    }, idToken);
  }, [currentNovelId, structureText, charactersText, worldText, userId, idToken, generate, clearMessages]);

  const handleStep2Confirm = useCallback(async () => {
    if (!currentNovelId) return;
    try {
      await saveStep2(currentNovelId, { plot: plotText });
      parseChaptersFromPlot(plotText);
      // Reload novel data to ensure chapters are populated correctly
      const refreshed = await refreshNovel(currentNovelId);
      if (refreshed?.chapters && typeof refreshed.chapters === "object") {
        setChapters(prev => prev.map(ch => {
          const loaded = refreshed.chapters?.[ch.num];
          return loaded ? { ...ch, status: "done" as const, content: loaded } : ch;
        }));
      }
      setStep(3);
      clearMessages();
      lastProcessedRef.current = 0;
    } catch (err) {
      alert("保存失败，请重试");
    }
  }, [currentNovelId, plotText, saveStep2, refreshNovel, clearMessages]);

  const handleChapterGenerate = useCallback(
    (chapterNum: number, outline?: string) => {
      const ch = chapters.find((c) => c.num === chapterNum);
      const chapterOutline = outline || ch?.outline || `第${chapterNum}章`;
      setGeneratingChapter(chapterNum);
      streamBuf.current.prose_writer = "";
      streamBuf.current.editor = "";
      setChapters((prev) =>
        prev.map((c) => c.num === chapterNum ? { ...c, status: "generating", content: "" } : c)
      );
      lastProcessedRef.current = 0;
      clearMessages();

      generate("/api/step3/chapter", {
        novel_id: currentNovelId,
        chapter_num: chapterNum,
        chapter_outline: chapterOutline,
        user_id: userId,
      }, idToken);
    },
    [chapters, currentNovelId, userId, idToken, generate, clearMessages]
  );

  const handleOutlineChange = useCallback((chapterNum: number, newOutline: string) => {
    setChapters((prev) =>
      prev.map((c) => c.num === chapterNum ? { ...c, outline: newOutline } : c)
    );
  }, []);

  const step1Tabs = useMemo(() => [
    { key: "structure", label: "📐 故事结构" },
    { key: "characters", label: "👤 角色设定" },
    { key: "world", label: "🌍 世界观" },
  ], []);

  const step1Values = useMemo(() => ({
    structure: structureText,
    characters: charactersText,
    world: worldText,
  }), [structureText, charactersText, worldText]);

  const hasStep1Results = structureText || charactersText || worldText;
  const hasStep2Results = plotText.trim().length > 0;

  return (
    <div style={styles.page}>
      <div style={styles.topBar}>
        <button onClick={onBack} style={styles.backBtn}>← 返回</button>
        <h2 style={styles.heading}>分步创作</h2>
        {generating && (
          <button onClick={cancel} style={styles.cancelBtn}>取消生成</button>
        )}
      </div>

      <StepProgress currentStep={step} />

      {/* ── STEP 1 ── */}
      {step === 1 && (
        <div style={styles.stepContent}>
          <StorySetup onSubmit={handleStep1Generate} disabled={generating} />

          {(generating || hasStep1Results) && (
            <div style={styles.resultSection}>
              <h3 style={styles.sectionLabel}>
                {generating ? "正在生成中..." : "生成结果（可编辑）"}
              </h3>
              <ResultEditor
                tabs={step1Tabs}
                values={step1Values}
                onChange={(key, value) => {
                  if (key === "structure") setStructureText(value);
                  if (key === "characters") setCharactersText(value);
                  if (key === "world") setWorldText(value);
                }}
                disabled={generating}
              />
              {hasStep1Results && !generating && (
                <>
                  <RefineChat
                    contextLabel="step1"
                    contextText={structureText + "\n\n" + charactersText + "\n\n" + worldText}
                    idToken={idToken}
                    novelId={currentNovelId}
                    onApply={(text) => {
                      // Apply to the active tab's content — default to structure
                      setStructureText(text);
                    }}
                  />
                  <button onClick={handleStep1Confirm} style={styles.confirmBtn}>
                    确认，进入下一步 →
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── STEP 2 ── */}
      {step === 2 && (
        <div style={styles.stepContent}>
          <Step1Summary structure={structureText} characters={charactersText} world={worldText} />

          <div style={styles.genRow}>
            <button onClick={() => setStep(1)} style={styles.backStepBtn}>← 返回上一步</button>
            <button onClick={handleStep2Generate} style={styles.generateBtn} disabled={generating}>
              {generating ? "生成中..." : "生成大纲"}
            </button>
          </div>

          {(generating || hasStep2Results) && (
            <div style={styles.resultSection}>
              <h3 style={styles.sectionLabel}>情节大纲{generating ? "（生成中...）" : "（可编辑）"}</h3>

              {/* While generating, show the raw streaming text */}
              {generating && (
                <textarea
                  value={plotText}
                  onChange={(e) => setPlotText(e.target.value)}
                  style={styles.plotTextarea}
                  placeholder="等待生成大纲..."
                  disabled={generating}
                />
              )}

              {/* After generation, show chapter-by-chapter abstracts */}
              {!generating && parsedAbstracts.length > 0 && (
                <div style={styles.abstractList}>
                  {parsedAbstracts.map((item) => {
                    const isOpen = expandedAbstract === item.num;
                    return (
                      <div key={item.num} style={styles.abstractCard}>
                        <div
                          style={styles.abstractHeader}
                          onClick={() => setExpandedAbstract(isOpen ? null : item.num)}
                        >
                          <span style={styles.abstractTitle}>
                            第{item.num}章：{item.title}
                          </span>
                          <span style={styles.abstractToggle}>{isOpen ? "▲" : "▼"}</span>
                        </div>
                        {isOpen && (
                          <div style={styles.abstractBody}>
                            <textarea
                              value={item.abstract}
                              onChange={(e) => {
                                const newVal = e.target.value;
                                setParsedAbstracts((prev) =>
                                  prev.map((a) =>
                                    a.num === item.num ? { ...a, abstract: newVal } : a
                                  )
                                );
                                // Rebuild full plotText from abstracts
                                const updated = parsedAbstracts.map((a) =>
                                  a.num === item.num
                                    ? `第${a.num}章：${a.title}\n${newVal}`
                                    : `第${a.num}章：${a.title}\n${a.abstract}`
                                );
                                setPlotText(updated.join("\n\n"));
                              }}
                              style={styles.abstractTextarea}
                              rows={4}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Fallback: if no parsed abstracts, show raw textarea */}
              {!generating && parsedAbstracts.length === 0 && hasStep2Results && (
                <textarea
                  value={plotText}
                  onChange={(e) => setPlotText(e.target.value)}
                  style={styles.plotTextarea}
                  placeholder="等待生成大纲..."
                />
              )}

              {hasStep2Results && !generating && (
                <>
                  <RefineChat
                    contextLabel="step2_plot"
                    contextText={plotText}
                    idToken={idToken}
                    novelId={currentNovelId}
                    onApply={(text) => {
                      setPlotText(text);
                      const abstracts = parsePlotToAbstracts(text);
                      if (abstracts.length > 0) setParsedAbstracts(abstracts);
                    }}
                  />
                  <button onClick={handleStep2Confirm} style={styles.confirmBtn}>
                    确认大纲 →
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── STEP 3 ── */}
      {step === 3 && (
        <div style={styles.stepContent}>
          <div style={styles.genRow}>
            <button onClick={() => setStep(2)} style={styles.backStepBtn}>← 返回上一步</button>
          </div>
          <ChapterList
            chapters={chapters}
            onGenerate={handleChapterGenerate}
            onOutlineChange={handleOutlineChange}
            generatingChapter={generatingChapter}
          />
        </div>
      )}
    </div>
  );
}

/* ── Step 1 Summary (collapsed) ── */
function Step1Summary({ structure, characters, world }: { structure: string; characters: string; world: string }) {
  const [expanded, setExpanded] = useState(false);
  if (!structure && !characters && !world) return null;

  const sections = [
    { label: "📐 故事结构", text: structure },
    { label: "👤 角色设定", text: characters },
    { label: "🌍 世界观", text: world },
  ].filter((s) => s.text);

  return (
    <div style={sumStyles.box}>
      <div style={sumStyles.header} onClick={() => setExpanded(!expanded)}>
        <span style={sumStyles.title}>✅ 第一步：基础设定</span>
        <span style={sumStyles.toggle}>{expanded ? "收起 ▲" : "展开 ▼"}</span>
      </div>
      {expanded && (
        <div style={sumStyles.body}>
          {sections.map((s) => (
            <div key={s.label} style={sumStyles.section}>
              <h4 style={sumStyles.label}>{s.label}</h4>
              <pre style={sumStyles.text}>{s.text.slice(0, 800)}{s.text.length > 800 ? "\n..." : ""}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const sumStyles: Record<string, React.CSSProperties> = {
  box: { background: "#111", border: "1px solid #1a3a1a", borderRadius: 10, overflow: "hidden" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", cursor: "pointer" },
  title: { color: "#10b981", fontSize: 14, fontWeight: 600 },
  toggle: { color: "#666", fontSize: 12 },
  body: { padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: 12, borderTop: "1px solid #222", paddingTop: 12 },
  section: { display: "flex", flexDirection: "column", gap: 4 },
  label: { color: "#888", fontSize: 12, fontWeight: 600 },
  text: { color: "#aaa", fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap", fontFamily: "inherit", margin: 0 },
};

const styles: Record<string, React.CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 16 },
  topBar: { display: "flex", alignItems: "center", gap: 16 },
  backBtn: { padding: "6px 16px", borderRadius: 6, border: "1px solid #333", background: "transparent", color: "#aaa", cursor: "pointer", fontSize: 13, fontFamily: "inherit" },
  heading: { fontSize: 22, color: "#c9a0dc", fontFamily: "'Georgia', serif", flex: 1 },
  cancelBtn: { padding: "6px 16px", borderRadius: 6, border: "1px solid #ef4444", background: "transparent", color: "#ef4444", cursor: "pointer", fontSize: 13, fontFamily: "inherit" },
  stepContent: { display: "flex", flexDirection: "column", gap: 20 },
  resultSection: { display: "flex", flexDirection: "column", gap: 16, background: "#0a0a0a", border: "1px solid #1a1a1a", borderRadius: 12, padding: 20 },
  sectionLabel: { color: "#888", fontSize: 14, fontWeight: 600 },
  genRow: { display: "flex", gap: 12, alignItems: "center" },
  backStepBtn: { padding: "8px 16px", borderRadius: 6, border: "1px solid #333", background: "transparent", color: "#aaa", cursor: "pointer", fontSize: 13, fontFamily: "inherit" },
  generateBtn: { padding: "12px 28px", borderRadius: 8, border: "none", background: "#7c3aed", color: "white", fontSize: 15, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" },
  confirmBtn: { padding: "12px 28px", borderRadius: 8, border: "none", background: "#10b981", color: "white", fontSize: 15, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", alignSelf: "flex-start" },
  plotTextarea: { width: "100%", minHeight: 300, maxHeight: 500, overflow: "auto", padding: 16, background: "#111", border: "1px solid #222", borderRadius: 10, color: "#e8e8e8", fontSize: 14, lineHeight: 1.8, fontFamily: "'Georgia', serif", resize: "vertical", outline: "none" },
  abstractList: { display: "flex", flexDirection: "column", gap: 8 },
  abstractCard: { background: "#111", border: "1px solid #222", borderRadius: 10, overflow: "hidden" },
  abstractHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", cursor: "pointer" },
  abstractTitle: { color: "#c9a0dc", fontSize: 14, fontWeight: 600 },
  abstractToggle: { color: "#555", fontSize: 11 },
  abstractBody: { padding: "0 16px 16px", borderTop: "1px solid #1a1a1a", paddingTop: 12 },
  abstractTextarea: { width: "100%", minHeight: 60, maxHeight: 200, overflow: "auto", padding: 12, background: "#0d0d0d", border: "1px solid #1a1a1a", borderRadius: 8, color: "#bbb", fontSize: 13, lineHeight: 1.7, fontFamily: "'Georgia', 'Times New Roman', serif", resize: "vertical", outline: "none" },
};
