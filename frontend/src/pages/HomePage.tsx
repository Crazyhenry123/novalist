import { useEffect, useCallback } from "react";
import type { PageView } from "../types";
import NovelList from "../components/NovelList";
import { useNovel } from "../hooks/useNovel";
import { useAuth } from "../auth/CognitoProvider";
import { useToast } from "../components/Toast";

interface Props {
  onNavigate: (page: PageView) => void;
  onSelectNovel: (novelId: string) => void;
}

export default function HomePage({ onNavigate, onSelectNovel }: Props) {
  const { novels, loading, listNovels, userId } = useNovel();
  const { idToken } = useAuth();
  const { toast } = useToast();

  useEffect(() => {
    listNovels();
  }, [listNovels]);

  const handleDelete = useCallback(async (novelId: string) => {
    try {
      const h: Record<string, string> = {};
      if (idToken) h["Authorization"] = `Bearer ${idToken}`;
      const res = await fetch(`/api/novel/${novelId}?user_id=${encodeURIComponent(userId)}`, {
        method: "DELETE",
        headers: h,
      });
      if (res.ok) {
        listNovels(); // Refresh list
      } else {
        toast("删除失败", "error");
      }
    } catch {
      alert("删除失败");
    }
  }, [userId, idToken, listNovels]);

  return (
    <div style={styles.page}>
      <h2 style={styles.heading}>开始创作</h2>

      <div style={styles.cardRow}>
        <div
          style={styles.modeCard}
          onClick={() => {
            onSelectNovel("");
            onNavigate("composer");
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "#7c3aed";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "#333";
          }}
        >
          <div style={styles.modeIcon}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#c9a0dc" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </div>
          <h3 style={styles.modeTitle}>分步创作</h3>
          <p style={styles.modeDesc}>架构 → 大纲 → 章节，三步完成你的小说</p>
          <div style={{ ...styles.modeBadge, background: "rgba(124,58,237,0.15)", color: "#c9a0dc" }}>
            推荐
          </div>
        </div>

        <div
          style={{ ...styles.modeCard, borderColor: "#1e3a5f" }}
          onClick={() => {
            onSelectNovel("");
            onNavigate("chat");
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "#3b82f6";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "#1e3a5f";
          }}
        >
          <div style={styles.modeIcon}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <h3 style={{ ...styles.modeTitle, color: "#60a5fa" }}>自由对话</h3>
          <p style={styles.modeDesc}>与 AI 自由交流，探索你的故事灵感</p>
          <div style={{ ...styles.modeBadge, background: "rgba(59,130,246,0.15)", color: "#60a5fa" }}>
            灵活
          </div>
        </div>
      </div>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>我的作品</h3>
        <NovelList
          novels={novels}
          loading={loading}
          onSelect={(novelId, page) => {
            onSelectNovel(novelId);
            onNavigate(page);
          }}
          onDelete={handleDelete}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: 32,
  },
  heading: {
    fontSize: 28,
    color: "#c9a0dc",
    fontFamily: "'Georgia', 'Times New Roman', serif",
  },
  cardRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 20,
  },
  modeCard: {
    position: "relative",
    background: "#111",
    border: "1px solid #333",
    borderRadius: 14,
    padding: 28,
    cursor: "pointer",
    transition: "border-color 0.2s",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  modeIcon: {
    marginBottom: 4,
  },
  modeTitle: {
    fontSize: 20,
    fontWeight: 700,
    color: "#c9a0dc",
    fontFamily: "'Georgia', 'Times New Roman', serif",
  },
  modeDesc: {
    color: "#888",
    fontSize: 14,
    lineHeight: 1.5,
  },
  modeBadge: {
    position: "absolute",
    top: 16,
    right: 16,
    fontSize: 11,
    padding: "3px 10px",
    borderRadius: 20,
    fontWeight: 600,
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  sectionTitle: {
    fontSize: 18,
    color: "#aaa",
    fontWeight: 600,
  },
};
