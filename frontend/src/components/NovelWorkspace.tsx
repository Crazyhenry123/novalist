import type { NovelRequest } from "../types";
import { useAuth } from "../auth/CognitoProvider";
import { useSSE } from "../hooks/useSSE";
import StorySetup from "./StorySetup";
import AgentThoughts from "./AgentThoughts";
import ChapterView from "./ChapterView";

export default function NovelWorkspace() {
  const { idToken } = useAuth();
  const { messages, generating, generate, cancel, clearMessages } = useSSE();

  function handleSubmit(req: NovelRequest) {
    clearMessages();
    generate("/api/generate", req as unknown as Record<string, unknown>, idToken);
  }

  return (
    <div>
      <StorySetup onSubmit={handleSubmit} disabled={generating} />

      {generating && (
        <div style={styles.progress}>
          <div style={styles.spinner} />
          <span>AI 智能体正在协作创作您的小说...</span>
          <button onClick={cancel} style={styles.cancelBtn}>
            取消
          </button>
        </div>
      )}

      {messages.length > 0 && (
        <div style={{ color: "#888", fontSize: 12, marginTop: 8 }}>
          已接收 {messages.length} 条消息
        </div>
      )}
      <AgentThoughts messages={messages} />
      <ChapterView messages={messages} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
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
  cancelBtn: {
    marginLeft: "auto",
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid #555",
    background: "transparent",
    color: "#ef4444",
    cursor: "pointer",
    fontSize: 13,
  },
};
