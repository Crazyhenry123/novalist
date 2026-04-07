import type { ReactNode } from "react";
import { useAuth } from "../auth/CognitoProvider";

export default function Layout({ children }: { children: ReactNode }) {
  const { email, logout } = useAuth();

  return (
    <div style={styles.wrapper}>
      <header style={styles.header}>
        <h1 style={styles.logo}>Novalist</h1>
        <div style={styles.headerRight}>
          <span style={styles.email}>{email}</span>
          <button onClick={logout} style={styles.logoutBtn}>
            退出登录
          </button>
        </div>
      </header>
      <main style={styles.main}>{children}</main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { minHeight: "100vh", background: "#0f0f0f" },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 32px",
    borderBottom: "1px solid #222",
    background: "#111",
  },
  logo: {
    fontSize: 24,
    color: "#c9a0dc",
    fontFamily: "'Georgia', serif",
    fontWeight: 700,
  },
  headerRight: { display: "flex", alignItems: "center", gap: 16 },
  email: { color: "#888", fontSize: 13 },
  logoutBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid #333",
    background: "transparent",
    color: "#aaa",
    cursor: "pointer",
    fontSize: 13,
  },
  main: { padding: 32, maxWidth: 1200, margin: "0 auto" },
};
