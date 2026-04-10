import { useState, useCallback, useEffect, createContext, useContext, type ReactNode } from "react";

interface ToastItem {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

interface ToastCtx {
  toast: (message: string, type?: "success" | "error" | "info") => void;
}

const ToastContext = createContext<ToastCtx>({ toast: () => {} });

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, type: "success" | "error" | "info" = "info") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div style={styles.container}>
        {toasts.map((t) => (
          <div key={t.id} style={{ ...styles.toast, ...typeStyles[t.type] }}>
            <span>{typeIcons[t.type]}</span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

const typeIcons: Record<string, string> = {
  success: "✓",
  error: "✕",
  info: "ℹ",
};

const typeStyles: Record<string, React.CSSProperties> = {
  success: { borderColor: "rgba(16,185,129,0.4)", background: "rgba(16,185,129,0.12)", color: "#10b981" },
  error: { borderColor: "rgba(239,68,68,0.4)", background: "rgba(239,68,68,0.12)", color: "#ef4444" },
  info: { borderColor: "rgba(124,58,237,0.4)", background: "rgba(124,58,237,0.12)", color: "#c9a0dc" },
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "fixed",
    top: 20,
    right: 20,
    zIndex: 9999,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    pointerEvents: "none",
  },
  toast: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid",
    fontSize: 14,
    fontWeight: 500,
    backdropFilter: "blur(12px)",
    animation: "fadeIn 0.2s ease",
    pointerEvents: "auto",
  },
};
