import { useState, useRef, useEffect, type KeyboardEvent } from "react";

interface ChatMessage {
  role: string;
  content: string;
}

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  streaming: boolean;
  streamingContent?: string;
}

export default function ChatPanel({ messages, onSend, streaming, streamingContent }: Props) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingContent]);

  function handleSend() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    onSend(text);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div style={styles.container}>
      <div ref={scrollRef} style={styles.messageArea}>
        {messages.map((msg, i) => {
          const isUser = msg.role === "user";
          return (
            <div key={i} style={{ ...styles.messageRow, justifyContent: isUser ? "flex-end" : "flex-start" }}>
              <div
                style={{
                  ...styles.bubble,
                  background: isUser ? "#7c3aed" : "#1a1a1a",
                  color: isUser ? "white" : "#e8e8e8",
                  borderBottomRightRadius: isUser ? 4 : 16,
                  borderBottomLeftRadius: isUser ? 16 : 4,
                }}
              >
                {!isUser && <span style={styles.roleLabel}>AI</span>}
                <div style={styles.messageContent}>{msg.content}</div>
              </div>
            </div>
          );
        })}
        {streaming && streamingContent && (
          <div style={{ ...styles.messageRow, justifyContent: "flex-start" }}>
            <div
              style={{
                ...styles.bubble,
                background: "#1a1a1a",
                color: "#e8e8e8",
                borderBottomLeftRadius: 4,
              }}
            >
              <span style={styles.roleLabel}>AI</span>
              <div style={styles.messageContent}>{streamingContent}</div>
            </div>
          </div>
        )}
        {streaming && !streamingContent && (
          <div style={{ ...styles.messageRow, justifyContent: "flex-start" }}>
            <div style={{ ...styles.bubble, background: "#1a1a1a", color: "#888" }}>
              <span style={styles.typingDots}>思考中...</span>
            </div>
          </div>
        )}
      </div>
      <div style={styles.inputArea}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的想法..."
          style={styles.input}
          rows={1}
          disabled={streaming}
        />
        <button
          onClick={handleSend}
          style={{
            ...styles.sendBtn,
            opacity: !input.trim() || streaming ? 0.5 : 1,
          }}
          disabled={!input.trim() || streaming}
        >
          发送
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    background: "#0f0f0f",
    borderRadius: 12,
    border: "1px solid #222",
    overflow: "hidden",
  },
  messageArea: {
    flex: 1,
    overflowY: "auto",
    padding: 20,
    display: "flex",
    flexDirection: "column",
    gap: 12,
    minHeight: 400,
  },
  messageRow: {
    display: "flex",
  },
  bubble: {
    maxWidth: "75%",
    padding: "10px 16px",
    borderRadius: 16,
    fontSize: 14,
    lineHeight: 1.7,
  },
  roleLabel: {
    display: "block",
    fontSize: 10,
    color: "#888",
    marginBottom: 4,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  messageContent: {
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  typingDots: {
    fontSize: 13,
    fontStyle: "italic",
  },
  inputArea: {
    display: "flex",
    gap: 8,
    padding: 16,
    borderTop: "1px solid #222",
    background: "#111",
  },
  input: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid #333",
    background: "#1a1a1a",
    color: "#e8e8e8",
    fontSize: 14,
    fontFamily: "inherit",
    resize: "none",
    outline: "none",
  },
  sendBtn: {
    padding: "10px 24px",
    borderRadius: 8,
    border: "none",
    background: "#7c3aed",
    color: "white",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
};
