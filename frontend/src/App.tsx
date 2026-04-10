import { useState } from "react";
import { AuthProvider } from "./auth/CognitoProvider";
import ProtectedRoute from "./auth/ProtectedRoute";
import { ToastProvider } from "./components/Toast";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import StepComposer from "./pages/StepComposer";
import FreeChatPage from "./pages/FreeChatPage";
import type { PageView } from "./types";

function AppRouter() {
  const [page, setPage] = useState<PageView>("home");
  const [novelId, setNovelId] = useState<string>("");

  return (
    <Layout novelId={novelId}>
      {page === "home" && (
        <HomePage
          onNavigate={setPage}
          onSelectNovel={setNovelId}
        />
      )}
      {page === "composer" && (
        <StepComposer
          novelId={novelId}
          onBack={() => setPage("home")}
        />
      )}
      {page === "chat" && (
        <FreeChatPage
          novelId={novelId}
          onBack={() => setPage("home")}
          onStartComposition={(id) => {
            setNovelId(id);
            setPage("composer");
          }}
        />
      )}
    </Layout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <ProtectedRoute>
          <AppRouter />
        </ProtectedRoute>
      </ToastProvider>
    </AuthProvider>
  );
}
