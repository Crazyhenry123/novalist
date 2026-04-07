import { useEffect, useRef } from "react";
import type { StreamMessage } from "../types";

interface Props {
  messages: StreamMessage[];
}

const AGENT_COLORS: Record<string, string> = {
  story_architect: "#f59e0b",
  character_developer: "#10b981",
  world_builder: "#3b82f6",
  plot_weaver: "#8b5cf6",
  prose_writer: "#ec4899",
  editor: "#06b6d4",
};

const AGENT_ICONS: Record<string, string> = {
  story_architect: "📐",
  character_developer: "👤",
  world_builder: "🌍",
  plot_weaver: "🧵",
  prose_writer: "✍️",
  editor: "📝",
};

const AGENT_NAMES_CN: Record<string, string> = {
  story_architect: "故事架构师",
  character_developer: "角色开发师",
  world_builder: "世界构建师",
  plot_weaver: "情节编织师",
  prose_writer: "文笔写手",
  editor: "编辑",
};

export default function AgentThoughts({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) return null;

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>智能体动态</h3>
      <div style={styles.feed}>
        {messages.map((msg, i) => {
          const agent = msg.agent || "";
          const agents = agent.split(",").map((a) => a.trim());
          const color = AGENT_COLORS[agents[0]] || "#888";
          const icon = agents.map((a) => AGENT_ICONS[a] || "🤖").join(" ");

          return (
            <div key={i} style={styles.message}>
              <span style={styles.icon}>{icon}</span>
              <div style={styles.body}>
                <span style={{ ...styles.agentName, color }}>
                  {agents.map((a) => AGENT_NAMES_CN[a] || a.replace(/_/g, " ")).join("、")}
                </span>
                <span style={styles.type}>{msg.type}</span>
                <p style={styles.content}>{msg.content}</p>
                {msg.data?.preview != null && (
                  <pre style={styles.preview}>
                    {String(msg.data.preview as string).slice(0, 300)}
                    {String(msg.data.preview as string).length > 300 ? "..." : ""}
                  </pre>
                )}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 12,
    padding: 20,
    marginTop: 24,
  },
  heading: { color: "#888", fontSize: 14, textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 },
  feed: { maxHeight: 500, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 },
  message: { display: "flex", gap: 12, alignItems: "flex-start" },
  icon: { fontSize: 20, flexShrink: 0, marginTop: 2 },
  body: { flex: 1 },
  agentName: { fontWeight: 600, fontSize: 13 },
  type: {
    marginLeft: 8,
    fontSize: 11,
    color: "#555",
    background: "#1a1a1a",
    padding: "2px 8px",
    borderRadius: 4,
  },
  content: { color: "#ccc", fontSize: 14, marginTop: 4, lineHeight: 1.5 },
  preview: {
    background: "#0a0a0a",
    border: "1px solid #222",
    borderRadius: 6,
    padding: 12,
    fontSize: 12,
    color: "#888",
    marginTop: 8,
    whiteSpace: "pre-wrap",
    maxHeight: 150,
    overflowY: "auto",
  },
};
