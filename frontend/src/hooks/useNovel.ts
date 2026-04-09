import { useState, useCallback } from "react";
import type { NovelState, NovelSummary } from "../types";
import { useAuth } from "../auth/CognitoProvider";

export function useNovel() {
  const { idToken, email } = useAuth();
  const [currentNovel, setCurrentNovel] = useState<NovelState | null>(null);
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const userId = email || "anonymous";

  const headers = useCallback((): Record<string, string> => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (idToken) h["Authorization"] = `Bearer ${idToken}`;
    return h;
  }, [idToken]);

  const loadNovel = useCallback(
    async (novelId: string) => {
      setLoading(true);
      try {
        const res = await fetch(`/api/novel/${novelId}`, { headers: headers() });
        if (!res.ok) throw new Error("Failed to load novel");
        const data: NovelState = await res.json();
        setCurrentNovel(data);
        return data;
      } catch (err) {
        console.error("loadNovel error:", err);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [headers]
  );

  const listNovels = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/novels?user_id=${encodeURIComponent(userId)}`, {
        headers: headers(),
      });
      if (!res.ok) throw new Error("Failed to list novels");
      const json = await res.json();
      const data: NovelSummary[] = json.novels || [];
      setNovels(data);
      return data;
    } catch (err) {
      console.error("listNovels error:", err);
      return [];
    } finally {
      setLoading(false);
    }
  }, [userId, headers]);

  const saveStep1 = useCallback(
    async (novelId: string, data: { structure?: string; characters?: string; world?: string }) => {
      const res = await fetch(`/api/novel/${novelId}/step1`, {
        method: "PUT",
        headers: headers(),
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to save step1");
      const json = await res.json();
      // Backend now returns full novel state
      if (json.novel_id) {
        setCurrentNovel(json as NovelState);
      }
      return json;
    },
    [headers]
  );

  const saveStep2 = useCallback(
    async (novelId: string, data: { plot?: string }) => {
      const res = await fetch(`/api/novel/${novelId}/step2`, {
        method: "PUT",
        headers: headers(),
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to save step2");
      const json = await res.json();
      // Backend now returns full novel state
      if (json.novel_id) {
        setCurrentNovel(json as NovelState);
      }
      return json;
    },
    [headers]
  );

  const refreshNovel = useCallback(
    async (novelId: string) => {
      try {
        const res = await fetch(`/api/novel/${novelId}`, { headers: headers() });
        if (!res.ok) throw new Error("Failed to refresh novel");
        const data: NovelState = await res.json();
        setCurrentNovel(data);
        return data;
      } catch (err) {
        console.error("refreshNovel error:", err);
        return null;
      }
    },
    [headers]
  );

  return {
    currentNovel,
    setCurrentNovel,
    novels,
    loading,
    loadNovel,
    listNovels,
    saveStep1,
    saveStep2,
    refreshNovel,
    userId,
  };
}
