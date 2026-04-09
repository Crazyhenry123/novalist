interface Props {
  currentStep: number;
}

const STEPS = [
  { num: 1, label: "基础设定" },
  { num: 2, label: "情节大纲" },
  { num: 3, label: "章节写作" },
];

export default function StepProgress({ currentStep }: Props) {
  return (
    <div style={styles.container}>
      {STEPS.map((step, i) => {
        const isActive = step.num === currentStep;
        const isCompleted = step.num < currentStep;
        const color = isCompleted ? "#10b981" : isActive ? "#7c3aed" : "#555";
        const bgColor = isCompleted ? "rgba(16,185,129,0.15)" : isActive ? "rgba(124,58,237,0.15)" : "transparent";

        return (
          <div key={step.num} style={styles.stepRow}>
            {i > 0 && (
              <div
                style={{
                  ...styles.line,
                  background: isCompleted ? "#10b981" : "#333",
                }}
              />
            )}
            <div
              style={{
                ...styles.step,
                borderColor: color,
                background: bgColor,
              }}
            >
              <span style={{ ...styles.num, color }}>{step.num}</span>
              <span style={{ ...styles.label, color: isActive ? "#e8e8e8" : isCompleted ? "#10b981" : "#666" }}>
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 0,
    marginBottom: 32,
  },
  stepRow: {
    display: "flex",
    alignItems: "center",
  },
  line: {
    width: 60,
    height: 2,
    flexShrink: 0,
  },
  step: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 20px",
    borderRadius: 8,
    border: "1px solid",
    whiteSpace: "nowrap",
  },
  num: {
    fontWeight: 700,
    fontSize: 16,
  },
  label: {
    fontSize: 14,
  },
};
