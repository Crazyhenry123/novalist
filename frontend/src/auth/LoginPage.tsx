import { useState, type FormEvent } from "react";
import { useAuth } from "./CognitoProvider";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Novalist</h1>
        <p style={styles.subtitle}>AI 智能小说创作平台</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="email"
            placeholder="邮箱地址"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={styles.input}
            required
          />
          <input
            type="password"
            placeholder="密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
            required
          />
          {error && <p style={styles.error}>{error}</p>}
          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    background: "linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 100%)",
  },
  card: {
    background: "#1e1e2e",
    borderRadius: 12,
    padding: "48px 40px",
    width: 400,
    boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
    textAlign: "center" as const,
  },
  title: {
    fontSize: 36,
    fontWeight: 700,
    color: "#c9a0dc",
    marginBottom: 4,
    fontFamily: "'Georgia', serif",
  },
  subtitle: {
    color: "#888",
    fontSize: 14,
    marginBottom: 32,
  },
  form: { display: "flex", flexDirection: "column" as const, gap: 16 },
  input: {
    padding: "12px 16px",
    borderRadius: 8,
    border: "1px solid #333",
    background: "#0f0f0f",
    color: "#e8e8e8",
    fontSize: 15,
    outline: "none",
  },
  button: {
    padding: "12px",
    borderRadius: 8,
    border: "none",
    background: "#7c3aed",
    color: "white",
    fontSize: 16,
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 8,
  },
  error: { color: "#ef4444", fontSize: 13 },
};
