import { useState, useCallback, useRef } from "react";
import type { StreamMessage } from "../types";

export function useSSE() {
  const [messages, setMessages] = useState<StreamMessage[]>([]);
  const [generating, setGenerating] = useState(false);
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  const generate = useCallback(
    (url: string, body: Record<string, unknown>, token: string | null) => {
      setMessages([]);
      setGenerating(true);

      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;
      let lastIndex = 0;

      xhr.open("POST", url);
      xhr.setRequestHeader("Content-Type", "application/json");
      if (token) {
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      }

      xhr.onprogress = () => {
        // Parse new data since last progress event
        const newData = xhr.responseText.substring(lastIndex);
        lastIndex = xhr.responseText.length;

        if (!newData) return;

        // Split into SSE events (separated by double newline)
        const parts = newData.split("\n\n");
        for (const part of parts) {
          const trimmed = part.trim();
          if (!trimmed || trimmed.startsWith(":")) continue; // Skip empty/comments (heartbeats)

          let eventType = "message";
          let data = "";

          for (const line of trimmed.split("\n")) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7);
            } else if (line.startsWith("data: ")) {
              data = line.slice(6);
            }
          }

          if (!data) continue;

          try {
            const parsed = JSON.parse(data);
            const msg: StreamMessage = {
              type: eventType,
              agent: parsed.agent,
              content: parsed.content,
              data: parsed,
              novel_id: parsed.novel_id,
              chapter: parsed.chapter,
              word_count: parsed.word_count,
            };

            setMessages((prev) => [...prev, msg]);

            if (eventType === "done" || eventType === "error") {
              setGenerating(false);
            }
          } catch {
            // Skip malformed JSON
          }
        }
      };

      xhr.onload = () => {
        // Trigger one final parse for any remaining data
        xhr.onprogress?.(null as unknown as ProgressEvent);
        setGenerating(false);
        xhrRef.current = null;
      };

      xhr.onerror = () => {
        setMessages((prev) => [
          ...prev,
          { type: "error", content: "连接错误：网络异常" },
        ]);
        setGenerating(false);
        xhrRef.current = null;
      };

      xhr.send(JSON.stringify(body));
    },
    []
  );

  const cancel = useCallback(() => {
    xhrRef.current?.abort();
    setGenerating(false);
    xhrRef.current = null;
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, generating, generate, cancel, clearMessages };
}
