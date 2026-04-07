import { useRef, useState, useCallback, useEffect } from "react";
import type { StreamMessage } from "../types";

const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || "ws://localhost:8080";
const RECONNECT_DELAY = 3000;
const MAX_RECONNECT = 5;

export function useWebSocket(token: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<StreamMessage[]>([]);

  const connect = useCallback(() => {
    if (!token) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const url = `${WS_URL}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setConnected(true);
      reconnectCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg: StreamMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev, msg]);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;

      if (reconnectCount.current < MAX_RECONNECT) {
        reconnectCount.current++;
        setTimeout(connect, RECONNECT_DELAY);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [token]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((action: string, payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, payload }));
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { connected, messages, sendMessage, clearMessages };
}
