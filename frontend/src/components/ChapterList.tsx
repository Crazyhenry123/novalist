import { useState } from "react";

type ChapterStatus = "pending" | "generating" | "done";

interface ChapterItem {
  num: number;
  outline: string;
  status: ChapterStatus;
  content?: string;
}

interface Props {
  chapters: ChapterItem[];
  onGenerate: (chapterNum: number, outline: string) => void;
  onOutlineChange?: (chapterNum: number, outline: string) => void;
  generatingChapter: number | null;
  generatingPhase?: "writing" | "editing";
}

export default function ChapterList({ chapters, onGenerate, onOutlineChange, generatingChapter, generatingPhase }: Props) {
  const [expandedChapter, setExpandedChapter] = useState<number | null>(null);
  const [confirmedOutlines, setConfirmedOutlines] = useState<Record<number, boolean>>({});

  const statusLabel = (status: ChapterStatus, chapterNum: number): string => {
    if (status === "generating" && chapterNum === generatingChapter) {
      return generatingPhase === "editing" ? "润色中..." : "初稿撰写中...";
    }
    switch (status) {
      case "pending": return "未生成";
      case "generating": return "生成中";
      case "done": return "已生成";
    }
  };

  const statusColor = (status: ChapterStatus): string => {
    switch (status) {
      case "pending": return "#666";
      case "generating": return "#f59e0b";
      case "done": return "#10b981";
    }
  };

  const handleConfirmOutline = (num: number) => {
    setConfirmedOutlines((prev) => ({ ...prev, [num]: true }));
  };

  const handleEditOutline = (num: number) => {
    setConfirmedOutlines((prev) => ({ ...prev, [num]: false }));
  };

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>章节列表</h3>
      {chapters.length === 0 && (
        <p style={styles.empty}>暂无章节，请先完成大纲生成</p>
      )}
      {chapters.map((ch) => {
        const isExpanded = expandedChapter === ch.num;
        const isGenerating = generatingChapter === ch.num;
        const outlineConfirmed = confirmedOutlines[ch.num] || false;

        return (
          <div key={ch.num} style={styles.chapter}>
            {/* Header */}
            <div
              style={styles.chapterHeader}
              onClick={() => setExpandedChapter(isExpanded ? null : ch.num)}
            >
              <div style={styles.chapterInfo}>
                <span style={styles.chapterNum}>第 {ch.num} 章</span>
                <span style={styles.chapterOutline}>
                  {ch.outline.length > 60 ? ch.outline.slice(0, 60) + "..." : ch.outline}
                </span>
              </div>
              <div style={styles.chapterActions}>
                <span
                  style={{
                    ...styles.statusBadge,
                    color: statusColor(ch.status),
                    borderColor: statusColor(ch.status),
                  }}
                >
                  {isGenerating ? statusLabel("generating", ch.num) : statusLabel(ch.status, ch.num)}
                </span>
                <span style={styles.expandIcon}>{isExpanded ? "▲" : "▼"}</span>
              </div>
            </div>

            {/* Expanded content */}
            {isExpanded && (
              <div style={styles.expandedBody}>
                {/* Outline / Abstract section */}
                <div style={styles.outlineSection}>
                  <div style={styles.outlineLabelRow}>
                    <span style={styles.outlineLabel}>章节摘要</span>
                    {outlineConfirmed && ch.status === "pending" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleEditOutline(ch.num); }}
                        style={styles.editOutlineBtn}
                      >
                        编辑摘要
                      </button>
                    )}
                  </div>
                  {outlineConfirmed ? (
                    <pre style={styles.outlineText}>{ch.outline}</pre>
                  ) : (
                    <textarea
                      value={ch.outline}
                      onChange={(e) => onOutlineChange?.(ch.num, e.target.value)}
                      style={styles.outlineTextarea}
                      placeholder="章节摘要..."
                      onClick={(e) => e.stopPropagation()}
                    />
                  )}
                </div>

                {/* Action buttons */}
                <div style={styles.actionRow}>
                  {!outlineConfirmed && ch.status === "pending" && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleConfirmOutline(ch.num); }}
                      style={styles.confirmOutlineBtn}
                    >
                      确认摘要
                    </button>
                  )}
                  {outlineConfirmed && ch.status === "pending" && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onGenerate(ch.num, ch.outline); }}
                      style={styles.genBtn}
                      disabled={generatingChapter !== null}
                    >
                      生成正文
                    </button>
                  )}
                  {ch.status === "done" && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onGenerate(ch.num, ch.outline); }}
                      style={styles.regenBtn}
                      disabled={generatingChapter !== null}
                    >
                      重新生成
                    </button>
                  )}
                </div>

                {/* Generated prose */}
                {(ch.status === "generating" || ch.status === "done") && ch.content && (
                  <div style={styles.proseSection}>
                    <div style={styles.proseLabelRow}>
                      <span style={styles.proseLabel}>正文内容</span>
                      {ch.status === "generating" && (
                        <span style={styles.generatingHint}>正在生成...</span>
                      )}
                    </div>
                    <div style={styles.chapterContent}>
                      {ch.content}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  heading: {
    color: "#888",
    fontSize: 14,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 8,
  },
  empty: {
    color: "#555",
    fontSize: 14,
    fontStyle: "italic",
  },
  chapter: {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 10,
    overflow: "hidden",
  },
  chapterHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 16px",
    gap: 16,
    cursor: "pointer",
  },
  chapterInfo: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    flex: 1,
    minWidth: 0,
  },
  chapterNum: {
    color: "#c9a0dc",
    fontWeight: 600,
    fontSize: 14,
    whiteSpace: "nowrap",
  },
  chapterOutline: {
    color: "#999",
    fontSize: 13,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  chapterActions: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexShrink: 0,
  },
  statusBadge: {
    fontSize: 11,
    padding: "3px 10px",
    borderRadius: 20,
    border: "1px solid",
    whiteSpace: "nowrap",
  },
  expandIcon: {
    color: "#555",
    fontSize: 11,
  },
  expandedBody: {
    borderTop: "1px solid #222",
    padding: 16,
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  outlineSection: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  outlineLabelRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  outlineLabel: {
    color: "#7c3aed",
    fontSize: 12,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  editOutlineBtn: {
    padding: "4px 12px",
    borderRadius: 4,
    border: "1px solid #333",
    background: "transparent",
    color: "#888",
    fontSize: 11,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  outlineText: {
    color: "#bbb",
    fontSize: 13,
    lineHeight: 1.7,
    whiteSpace: "pre-wrap",
    fontFamily: "'Georgia', 'Times New Roman', serif",
    margin: 0,
    padding: 12,
    background: "#0d0d0d",
    borderRadius: 8,
    border: "1px solid #1a1a1a",
  },
  outlineTextarea: {
    width: "100%",
    minHeight: 80,
    maxHeight: 200,
    padding: 12,
    background: "#0d0d0d",
    border: "1px solid #1a1a1a",
    borderRadius: 8,
    color: "#bbb",
    fontSize: 13,
    lineHeight: 1.7,
    fontFamily: "'Georgia', 'Times New Roman', serif",
    resize: "vertical",
    outline: "none",
    overflow: "auto",
  },
  actionRow: {
    display: "flex",
    gap: 10,
    alignItems: "center",
  },
  confirmOutlineBtn: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    background: "#10b981",
    color: "white",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  genBtn: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    background: "#7c3aed",
    color: "white",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  regenBtn: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "1px solid #444",
    background: "transparent",
    color: "#888",
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  proseSection: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    borderTop: "1px solid #1a1a1a",
    paddingTop: 16,
  },
  proseLabelRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  proseLabel: {
    color: "#10b981",
    fontSize: 12,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  generatingHint: {
    color: "#f59e0b",
    fontSize: 11,
  },
  chapterContent: {
    padding: 16,
    color: "#ddd",
    fontSize: 15,
    lineHeight: 2,
    fontFamily: "'Georgia', 'Times New Roman', serif",
    whiteSpace: "pre-wrap",
    background: "#0a0a0a",
    borderRadius: 8,
    border: "1px solid #1a1a1a",
    maxHeight: 500,
    overflow: "auto",
  },
};
