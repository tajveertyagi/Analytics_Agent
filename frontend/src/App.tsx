import { useEffect, useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import { createSession, deleteSession, getMe, listSessions, type ChatSessionOut } from "./api";

function App() {
  const [sessions, setSessions] = useState<ChatSessionOut[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const refreshSessions = useCallback(async () => {
    const list = await listSessions();
    setSessions(list);
    return list;
  }, []);

  useEffect(() => {
    (async () => {
      await getMe();
      const list = await refreshSessions();
      if (list.length > 0) {
        setActiveId(list[0].id);
      } else {
        const s = await createSession();
        setSessions([s]);
        setActiveId(s.id);
      }
      setReady(true);
    })();
  }, [refreshSessions]);

  const handleNew = useCallback(async () => {
    const s = await createSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
  }, []);

  const handleDelete = useCallback(
    async (id: string) => {
      await deleteSession(id);
      const remaining = sessions.filter((s) => s.id !== id);
      setSessions(remaining);
      if (activeId === id) {
        setActiveId(remaining[0]?.id ?? null);
      }
    },
    [sessions, activeId],
  );

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-400">
        Loading Sarthi...
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-slate-900">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={handleNew}
        onDelete={handleDelete}
      />
      <ChatWindow sessionId={activeId} onFirstMessage={refreshSessions} />
    </div>
  );
}

export default App;
