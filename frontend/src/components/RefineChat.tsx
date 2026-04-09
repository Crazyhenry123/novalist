import { useState, useRef, useCallback } from "react";

interface Props {
  /** Context description, e.g. "step1_structure" */
  contextLabel: string;
  /** Current text content that the user wants to refine */
  contextText: string;
  /** Auth token */
  idToken: string | null;
  /** Novel ID */
  novelId: string;
  /** Called when AI produces a response the user can apply */
  onApply?: (text: string) => void;
}

export default function RefineChat({
  contextLabel,
  contextText,
  idToken,
  novelId,
  onApply,
}: Props) {
  const [input, setInput] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setResponse("");
    setLoading(true);

    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr;
    let lastIndex = 0;
    let accumulated = "";

    xhr.open("POST", "/api/chat");
    xhr.setRequestHeader("Content-Type", "application/json");
    if (idToken) {
      xhr.setRequestHeader("Authorization", `Bearer ${idToken}`);
    }

    xhr.onprogress = () => {
      const newData = xhr.responseText.substring(lastIndex);
      lastIndex = xhr.responseText.length;
      if (!newData) return;

      const parts = newData.split("\n\n");
      for (const part of parts) {
        const trimmedPart = part.trim();
        if (!trimmedPart || trimmedPart.startsWith(":")) continue;

        let data = "";
        for (const line of trimmedPart.split("\n")) {
          if (line.startsWith("data: ")) {
            data = line.slice(6);
          }
        }
        if (!data) continue;

        try {
          const parsed = JSON.parse(data);
          if (parsed.content) {
            accumulated += parsed.content;
            setResponse(accumulated);
          }
        } catch {
          // skip
        }
      }
    };

    xhr.onload = () => {
      xhr.onprogress?.(null as unknown as ProgressEvent);
      setLoading(false);
      xhrRef.current = null;
    };

    xhr.onerror = () => {
      setResponse("请求失败，请重试。");
      setLoading(false);
      xhrRef.current = null;
    };

    xhr.send(
      JSON.stringify({
        novel_id: novelId,
        context_label: contextLabel,
        context_text: contextText.slice(0, 4000),
        message: trimmed,
      })
    );
  }, [input, loading, idToken, novelId, contextLabel, contextText]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.label}>优化建议</span>
        <span style={styles.hint}>输入修改指令，如"让主角更有个性"</span>
      </div>
      <div style={styles.inputRow}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入优化指令..."
          style={styles.input}
          disabled={loading}
        />
        <button
          onClick={handleSend}
          style={{
            ...styles.sendBtn,
            opacity: loading || !input.trim() ? 0.5 : 1,
          }}
          disabled={loading || !input.trim()}
        >
          {loading ? "思考中..." : "发送"}
        </button>
      </div>
      {response && (
        <div style={styles.responseArea}>
          <pre style={styles.responseText}>{response}</pre>
          {onApply && !loading && (
            <button
              onClick={() => onApply(response)}
              style={styles.applyBtn}
            >
              应用到文本
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "#0d0d0d",
    border: "1px solid #1a1a1a",
    borderRadius: 10,
    padding: 16,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  label: {
    color: "#7c3aed",
    fontSize: 13,
    fontWeight: 600,
  },
  hint: {
    color: "#555",
    fontSize: 12,
  },
  inputRow: {
    display: "flex",
    gap: 8,
  },
  input: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid #222",
    background: "#111",
    color: "#e8e8e8",
    fontSize: 13,
    fontFamily: "inherit",
    outline: "none",
  },
  sendBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    background: "#7c3aed",
    color: "white",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
  responseArea: {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 8,
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  responseText: {
    color: "#ccc",
    fontSize: 13,
    lineHeight: 1.7,
    whiteSpace: "pre-wrap",
    fontFamily: "'Georgia', 'Times New Roman', serif",
    margin: 0,
    maxHeight: 300,
    overflow: "auto",
  },
  applyBtn: {
    alignSelf: "flex-end",
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid #10b981",
    background: "transparent",
    color: "#10b981",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
  },
};
