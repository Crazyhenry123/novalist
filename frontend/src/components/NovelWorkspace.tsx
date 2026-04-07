import { useState, useEffect } from "react";
import type { NovelRequest } from "../types";
import { useAuth } from "../auth/CognitoProvider";
import { useWebSocket } from "../hooks/useWebSocket";
import StorySetup from "./StorySetup";
import AgentThoughts from "./AgentThoughts";
import ChapterView from "./ChapterView";

export default function NovelWorkspace() {
  const { idToken } = useAuth();
  const { connected, messages, sendMessage, clearMessages } = useWebSocket(idToken);
  const [generating, setGenerating] = useState(false);

  function handleSubmit(req: NovelRequest) {
    clearMessages();
    setGenerating(true);
    sendMessage("start_novel", req as unknown as Record<string, unknown>);
  }

  const isComplete = messages.some(
    (m) => m.type === "novel_complete" || m.type === "error"
  );

  useEffect(() => {
    if (isComplete && generating) {
      setGenerating(false);
    }
  }, [isComplete, generating]);

  return (
    <div>
      <div style={styles.status}>
        <span
          style={{
            ...styles.dot,
            background: connected ? "#10b981" : "#ef4444",
          }}
        />
        {connected ? "已连接" : "未连接"}
      </div>

      <StorySetup onSubmit={handleSubmit} disabled={generating} />

      {generating && (
        <div style={styles.progress}>
          <div style={styles.spinner} />
          <span>AI 智能体正在协作创作您的小说...</span>
        </div>
      )}

      <AgentThoughts messages={messages} />
      <ChapterView messages={messages} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  status: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    color: "#888",
    fontSize: 12,
    marginBottom: 24,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
  },
  progress: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    color: "#c9a0dc",
    fontSize: 15,
    marginTop: 24,
    padding: 16,
    background: "#1a1a2e",
    borderRadius: 8,
  },
  spinner: {
    width: 20,
    height: 20,
    border: "2px solid #333",
    borderTopColor: "#7c3aed",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
};
