import type { StreamMessage } from "../types";

interface Props {
  messages: StreamMessage[];
}

export default function ChapterView({ messages }: Props) {
  const chapterMessages = messages.filter(
    (m) => m.type === "chapter_complete" || m.type === "prose_chunk"
  );

  if (chapterMessages.length === 0) return null;

  const chapters: Map<number, string> = new Map();
  for (const msg of chapterMessages) {
    const ch = msg.chapter ?? 0;
    const existing = chapters.get(ch) || "";
    chapters.set(ch, existing + (msg.content || ""));
  }

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>章节内容</h3>
      {Array.from(chapters.entries()).map(([num, text]) => (
        <div key={num} style={styles.chapter}>
          <h4 style={styles.chapterTitle}>第{num}章</h4>
          <div style={styles.prose}>{text}</div>
        </div>
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { marginTop: 32 },
  heading: {
    color: "#888",
    fontSize: 14,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 16,
  },
  chapter: {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 12,
    padding: 24,
    marginBottom: 16,
  },
  chapterTitle: {
    fontSize: 20,
    color: "#c9a0dc",
    fontFamily: "'Georgia', serif",
    marginBottom: 16,
  },
  prose: {
    color: "#ddd",
    fontSize: 15,
    lineHeight: 1.8,
    fontFamily: "'Georgia', serif",
    whiteSpace: "pre-wrap",
  },
};
