import { useState, useEffect } from "react";
import { useAuth } from "../auth/CognitoProvider";
import type { UserMemory } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  novelId?: string;
}

export default function MemoryPanel({ open, onClose, novelId }: Props) {
  const { email, idToken } = useAuth();
  const [memory, setMemory] = useState<UserMemory | null>(null);
  const [loading, setLoading] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const userId = email || "anonymous";

  useEffect(() => {
    if (open && novelId) {
      setLoading(true);
      const h: Record<string, string> = { "Content-Type": "application/json" };
      if (idToken) h["Authorization"] = `Bearer ${idToken}`;
      fetch(`/api/memory?user_id=${encodeURIComponent(userId)}&novel_id=${encodeURIComponent(novelId)}`, { headers: h })
        .then((r) => r.json())
        .then((data: UserMemory) => {
          setMemory(data);
          setNotes(data.user_preferences?.notes || "");
        })
        .catch((err) => console.error("Failed to load memory:", err))
        .finally(() => setLoading(false));
    } else if (open && !novelId) {
      setMemory(null);
      setLoading(false);
    }
  }, [open, userId, idToken, novelId]);

  const handleSaveNotes = async () => {
    if (!memory) return;
    setSaving(true);
    try {
      const h: Record<string, string> = { "Content-Type": "application/json" };
      if (idToken) h["Authorization"] = `Bearer ${idToken}`;
      const updated: UserMemory = {
        ...memory,
        user_preferences: {
          ...memory.user_preferences,
          notes,
        },
      };
      const res = await fetch(`/api/memory?novel_id=${encodeURIComponent(novelId || "")}`, {
        method: "PUT",
        headers: h,
        body: JSON.stringify({ user_id: userId, memory: updated }),
      });
      if (res.ok) {
        const data = await res.json();
        setMemory(data.memory || updated);
      }
    } catch (err) {
      console.error("Failed to save memory:", err);
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <>
      <div style={styles.overlay} onClick={onClose} />
      <div style={styles.panel}>
        <div style={styles.header}>
          <h3 style={styles.title}>记忆面板</h3>
          <button onClick={onClose} style={styles.closeBtn}>
            &times;
          </button>
        </div>

        {loading && <div style={styles.loading}>加载中...</div>}

        {!loading && memory && (
          <div style={styles.body}>
            {/* Current novel info */}
            {memory.current_novel?.novel_id && (
              <section style={styles.section}>
                <h4 style={styles.sectionTitle}>当前小说</h4>
                {memory.current_novel.title && (
                  <div style={styles.field}>
                    <span style={styles.fieldLabel}>标题:</span>
                    <span style={styles.fieldValue}>{memory.current_novel.title}</span>
                  </div>
                )}
                {memory.current_novel.key_characters && memory.current_novel.key_characters.length > 0 && (
                  <div style={styles.field}>
                    <span style={styles.fieldLabel}>主要角色:</span>
                    <span style={styles.fieldValue}>{memory.current_novel.key_characters.join(", ")}</span>
                  </div>
                )}
                {memory.current_novel.plot_summary && (
                  <div style={styles.field}>
                    <span style={styles.fieldLabel}>情节概要:</span>
                    <span style={styles.fieldValue}>{memory.current_novel.plot_summary}</span>
                  </div>
                )}
                {memory.current_novel.world_summary && (
                  <div style={styles.field}>
                    <span style={styles.fieldLabel}>世界观:</span>
                    <span style={styles.fieldValue}>{memory.current_novel.world_summary}</span>
                  </div>
                )}
                {memory.current_novel.chapters_written && memory.current_novel.chapters_written.length > 0 && (
                  <div style={styles.field}>
                    <span style={styles.fieldLabel}>已写章节:</span>
                    <span style={styles.fieldValue}>{memory.current_novel.chapters_written.join(", ")}</span>
                  </div>
                )}
              </section>
            )}

            {/* User preferences */}
            <section style={styles.section}>
              <h4 style={styles.sectionTitle}>偏好设置</h4>
              {memory.user_preferences?.preferred_style && (
                <div style={styles.field}>
                  <span style={styles.fieldLabel}>风格:</span>
                  <span style={styles.fieldValue}>{memory.user_preferences.preferred_style}</span>
                </div>
              )}
              {memory.user_preferences?.preferred_genre && (
                <div style={styles.field}>
                  <span style={styles.fieldLabel}>类型:</span>
                  <span style={styles.fieldValue}>{memory.user_preferences.preferred_genre}</span>
                </div>
              )}
            </section>

            {/* Editable notes */}
            <section style={styles.section}>
              <h4 style={styles.sectionTitle}>备注</h4>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="在此记录创作笔记..."
                style={styles.notesTextarea}
                rows={5}
              />
              <button onClick={handleSaveNotes} disabled={saving} style={styles.saveBtn}>
                {saving ? "保存中..." : "保存备注"}
              </button>
            </section>

            {/* Chat history summary */}
            {memory.chat_history_summary && (
              <section style={styles.section}>
                <h4 style={styles.sectionTitle}>对话摘要</h4>
                <p style={styles.summaryText}>{memory.chat_history_summary}</p>
              </section>
            )}

            {memory.updated_at && (
              <div style={styles.updatedAt}>
                最后更新: {new Date(memory.updated_at * 1000).toLocaleString("zh-CN")}
              </div>
            )}
          </div>
        )}

        {!loading && !memory && (
          <div style={styles.empty}>暂无记忆数据</div>
        )}
      </div>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: "rgba(0, 0, 0, 0.6)",
    zIndex: 999,
  },
  panel: {
    position: "fixed",
    top: 0,
    right: 0,
    bottom: 0,
    width: 400,
    background: "#1a1a1a",
    borderLeft: "1px solid #333",
    zIndex: 1000,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 20px",
    borderBottom: "1px solid #333",
    flexShrink: 0,
  },
  title: {
    color: "#c9a0dc",
    fontSize: 18,
    fontWeight: 600,
    margin: 0,
  },
  closeBtn: {
    background: "transparent",
    border: "none",
    color: "#888",
    fontSize: 24,
    cursor: "pointer",
    padding: "0 4px",
    lineHeight: 1,
  },
  loading: {
    color: "#888",
    padding: 32,
    textAlign: "center",
    fontSize: 14,
  },
  body: {
    flex: 1,
    overflowY: "auto",
    padding: 20,
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  section: {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 10,
    padding: 16,
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  sectionTitle: {
    color: "#10b981",
    fontSize: 14,
    fontWeight: 600,
    margin: 0,
    marginBottom: 4,
  },
  field: {
    display: "flex",
    gap: 8,
    fontSize: 13,
    lineHeight: 1.5,
  },
  fieldLabel: {
    color: "#666",
    flexShrink: 0,
    minWidth: 70,
  },
  fieldValue: {
    color: "#ccc",
  },
  notesTextarea: {
    width: "100%",
    padding: 12,
    background: "#0d0d0d",
    border: "1px solid #222",
    borderRadius: 8,
    color: "#ccc",
    fontSize: 13,
    lineHeight: 1.6,
    fontFamily: "inherit",
    resize: "vertical",
    outline: "none",
  },
  saveBtn: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    background: "#7c3aed",
    color: "white",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    alignSelf: "flex-start",
  },
  summaryText: {
    color: "#aaa",
    fontSize: 13,
    lineHeight: 1.6,
    margin: 0,
  },
  updatedAt: {
    color: "#555",
    fontSize: 11,
    textAlign: "right",
  },
  empty: {
    color: "#666",
    padding: 32,
    textAlign: "center",
    fontSize: 14,
  },
};
