import { useState, useCallback, useEffect, useRef } from "react";
import ChatPanel from "../components/ChatPanel";
import { useSSE } from "../hooks/useSSE";
import { useAuth } from "../auth/CognitoProvider";
import { useToast } from "../components/Toast";

interface Props {
  novelId: string;
  onBack: () => void;
  onStartComposition: (novelId: string) => void;
}

interface ChatMessage {
  role: string;
  content: string;
}

export default function FreeChatPage({ novelId, onBack, onStartComposition }: Props) {
  const { idToken, email } = useAuth();
  const { toast } = useToast();
  const userId = email || "anonymous";
  const { messages: sseMessages, generating, generate, clearMessages } = useSSE();
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [currentNovelId, setCurrentNovelId] = useState(novelId);
  const [streamingContent, setStreamingContent] = useState("");
  const lastProcessedRef = useRef(0);

  // Aggregate streaming content from SSE messages
  useEffect(() => {
    let newContent = "";
    let newNovelId = currentNovelId;

    for (let i = lastProcessedRef.current; i < sseMessages.length; i++) {
      const msg = sseMessages[i];
      if (msg.type === "text_chunk" && msg.content) {
        newContent += msg.content;
      }
      if (msg.novel_id) {
        newNovelId = msg.novel_id;
      }
      if (msg.type === "done") {
        // Finalize the assistant message
        const finalContent = streamingContent + newContent;
        if (finalContent) {
          setChatHistory((prev) => [...prev, { role: "assistant", content: finalContent }]);
        }
        setStreamingContent("");
        lastProcessedRef.current = sseMessages.length;
        if (newNovelId !== currentNovelId) {
          setCurrentNovelId(newNovelId);
        }
        return;
      }
      if (msg.type === "error") {
        const errorContent = msg.content || "发生错误，请重试";
        setChatHistory((prev) => [...prev, { role: "assistant", content: errorContent }]);
        setStreamingContent("");
        lastProcessedRef.current = sseMessages.length;
        return;
      }
    }

    if (newContent) {
      setStreamingContent((prev) => prev + newContent);
    }
    lastProcessedRef.current = sseMessages.length;

    if (newNovelId !== currentNovelId) {
      setCurrentNovelId(newNovelId);
    }
  }, [sseMessages, currentNovelId, streamingContent]);

  const handleSend = useCallback(
    (text: string) => {
      const userMessage: ChatMessage = { role: "user", content: text };
      setChatHistory((prev) => [...prev, userMessage]);
      setStreamingContent("");
      lastProcessedRef.current = 0;
      clearMessages();

      const body: Record<string, unknown> = {
        message: text,
        user_id: userId,
        chat_history: [...chatHistory, userMessage],
      };
      if (currentNovelId) {
        body.novel_id = currentNovelId;
      }

      generate(`/api/chat?user_id=${encodeURIComponent(userId)}`, body, idToken);
    },
    [chatHistory, currentNovelId, userId, idToken, generate, clearMessages]
  );

  const handleSaveAsProject = useCallback(async () => {
    try {
      const res = await fetch("/api/chat/save", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          user_id: userId,
          novel_id: currentNovelId || undefined,
          chat_history: chatHistory,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.novel_id) {
          setCurrentNovelId(data.novel_id);
        }
        toast("已保存为项目", "success");
      }
    } catch {
      toast("保存失败，请重试", "error");
    }
  }, [chatHistory, currentNovelId, userId, idToken]);

  const handleStartComposition = useCallback(() => {
    if (currentNovelId) {
      onStartComposition(currentNovelId);
    } else {
      // Save first, then navigate
      fetch("/api/chat/save", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
        },
        body: JSON.stringify({
          user_id: userId,
          chat_history: chatHistory,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.novel_id) {
            onStartComposition(data.novel_id);
          }
        })
        .catch(() => {
          toast("保存失败，请重试", "error");
        });
    }
  }, [currentNovelId, chatHistory, userId, idToken, onStartComposition]);

  return (
    <div style={styles.page}>
      <div style={styles.topBar}>
        <button onClick={onBack} style={styles.backBtn}>
          ← 返回
        </button>
        <h2 style={styles.heading}>自由对话</h2>
        <div style={styles.topActions}>
          {chatHistory.length > 0 && (
            <>
              <button onClick={handleSaveAsProject} style={styles.actionBtn}>
                保存为项目
              </button>
              <button onClick={handleStartComposition} style={styles.composeBtn}>
                开始创作
              </button>
            </>
          )}
        </div>
      </div>

      <div style={styles.chatWrapper}>
        <ChatPanel
          messages={chatHistory}
          onSend={handleSend}
          streaming={generating}
          streamingContent={streamingContent}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
    height: "calc(100vh - 120px)",
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  backBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid #333",
    background: "transparent",
    color: "#aaa",
    cursor: "pointer",
    fontSize: 13,
    fontFamily: "inherit",
  },
  heading: {
    fontSize: 22,
    color: "#60a5fa",
    fontFamily: "'Georgia', 'Times New Roman', serif",
    flex: 1,
  },
  topActions: {
    display: "flex",
    gap: 8,
  },
  actionBtn: {
    padding: "8px 16px",
    borderRadius: 6,
    border: "1px solid #333",
    background: "transparent",
    color: "#aaa",
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  composeBtn: {
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
  chatWrapper: {
    flex: 1,
    minHeight: 0,
  },
};
