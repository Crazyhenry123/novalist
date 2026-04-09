import { useState, useRef, useEffect } from "react";

interface Tab {
  key: string;
  label: string;
}

interface Props {
  tabs: Tab[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSave?: () => void;
  disabled?: boolean;
}

export default function ResultEditor({ tabs, values, onChange, onSave, disabled }: Props) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.key || "");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea up to maxHeight
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(500, Math.max(200, el.scrollHeight)) + "px";
    }
  }, [activeTab, values]);

  const currentValue = values[activeTab] || "";

  return (
    <div style={styles.container}>
      <div style={styles.tabBar}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              ...styles.tab,
              ...(activeTab === tab.key ? styles.tabActive : {}),
            }}
          >
            {tab.label}
          </button>
        ))}
        {onSave && (
          <button onClick={onSave} style={styles.saveBtn} disabled={disabled}>
            保存
          </button>
        )}
      </div>
      <textarea
        ref={textareaRef}
        value={currentValue}
        onChange={(e) => onChange(activeTab, e.target.value)}
        style={styles.textarea}
        placeholder="等待生成..."
        disabled={disabled}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: "#111",
    border: "1px solid #222",
    borderRadius: 12,
    overflow: "hidden",
  },
  tabBar: {
    display: "flex",
    alignItems: "center",
    gap: 0,
    borderBottom: "1px solid #222",
    background: "#0d0d0d",
  },
  tab: {
    padding: "10px 20px",
    background: "transparent",
    border: "none",
    borderBottom: "2px solid transparent",
    color: "#888",
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  tabActive: {
    color: "#c9a0dc",
    borderBottomColor: "#7c3aed",
    background: "rgba(124,58,237,0.08)",
  },
  saveBtn: {
    marginLeft: "auto",
    marginRight: 12,
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid #333",
    background: "transparent",
    color: "#aaa",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  textarea: {
    width: "100%",
    minHeight: 200,
    maxHeight: 500,
    overflow: "auto",
    padding: 16,
    background: "#111",
    border: "none",
    color: "#e8e8e8",
    fontSize: 14,
    lineHeight: 1.8,
    fontFamily: "'Georgia', 'Times New Roman', serif",
    resize: "vertical",
    outline: "none",
  },
};
