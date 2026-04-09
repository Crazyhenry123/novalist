import type { NovelSummary, NovelStatus, PageView } from "../types";

interface Props {
  novels: NovelSummary[];
  onSelect: (novelId: string, page: PageView) => void;
  loading: boolean;
}

const STATUS_MAP: Record<NovelStatus, { label: string; color: string }> = {
  chat: { label: "对话中", color: "#3b82f6" },
  step1_draft: { label: "构思中", color: "#f59e0b" },
  step1_done: { label: "架构完成", color: "#f59e0b" },
  step2_draft: { label: "大纲生成中", color: "#8b5cf6" },
  step2_done: { label: "大纲完成", color: "#8b5cf6" },
  writing: { label: "写作中", color: "#ec4899" },
  completed: { label: "已完成", color: "#10b981" },
};

function getTargetPage(status: NovelStatus): PageView {
  if (status === "chat") return "chat";
  return "composer";
}

function formatDate(ts?: number): string {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

export default function NovelList({ novels, onSelect, loading }: Props) {
  if (loading) {
    return <p style={{ color: "#666", fontSize: 14 }}>加载中...</p>;
  }

  if (novels.length === 0) {
    return <p style={{ color: "#555", fontSize: 14 }}>还没有作品，开始创作吧！</p>;
  }

  return (
    <div style={styles.list}>
      {novels.map((novel) => {
        const statusInfo = STATUS_MAP[novel.status] || { label: novel.status, color: "#888" };
        const title = novel.title || (novel.premise ? novel.premise.slice(0, 40) + "..." : "未命名作品");

        return (
          <div
            key={novel.novel_id}
            style={styles.card}
            onClick={() => onSelect(novel.novel_id, getTargetPage(novel.status))}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = "#444";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.borderColor = "#222";
            }}
          >
            <div style={styles.cardTop}>
              <h4 style={styles.title}>{title}</h4>
              <span
                style={{
                  ...styles.badge,
                  color: statusInfo.color,
                  borderColor: statusInfo.color,
                }}
              >
                {statusInfo.label}
              </span>
            </div>
            {novel.premise && (
              <p style={styles.premise}>
                {novel.premise.length > 80 ? novel.premise.slice(0, 80) + "..." : novel.premise}
              </p>
            )}
            {novel.created_at && (
              <span style={styles.date}>{formatDate(novel.created_at)}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  list: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  card: {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 10,
    padding: "16px 20px",
    cursor: "pointer",
    transition: "border-color 0.2s",
  },
  cardTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  title: {
    color: "#e8e8e8",
    fontSize: 15,
    fontWeight: 600,
    fontFamily: "'Georgia', 'Times New Roman', serif",
    flex: 1,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  badge: {
    fontSize: 11,
    padding: "3px 10px",
    borderRadius: 20,
    border: "1px solid",
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
  premise: {
    color: "#888",
    fontSize: 13,
    marginTop: 8,
    lineHeight: 1.5,
  },
  date: {
    color: "#555",
    fontSize: 11,
    marginTop: 8,
    display: "inline-block",
  },
};
