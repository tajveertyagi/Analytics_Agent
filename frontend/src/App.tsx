import { useEffect, useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import { createSession, deleteSession, getMe, listSessions, type ChatSessionOut } from "./api";

// Remembers which chat this browser had open, so a reload reopens that exact
// conversation (ChatGPT does the same via its /c/<id> URL) instead of always
// jumping to whichever session was most recently active.
const LAST_SESSION_KEY = "sarthi:lastSessionId";

function readLastSessionId(): string | null {
  try {
    return localStorage.getItem(LAST_SESSION_KEY);
  } catch {
    return null;
  }
}

function writeLastSessionId(id: string | null) {
  try {
    if (id) localStorage.setItem(LAST_SESSION_KEY, id);
    else localStorage.removeItem(LAST_SESSION_KEY);
  } catch {
    // localStorage unavailable (private browsing, storage blocked) -- fine, just no memory across reloads.
  }
}

function App() {
  const [sessions, setSessions] = useState<ChatSessionOut[]>([]);
  const [activeId, setActiveIdState] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const setActiveId = useCallback((id: string | null) => {
    setActiveIdState(id);
    writeLastSessionId(id);
  }, []);

  const refreshSessions = useCallback(async () => {
    const list = await listSessions();
    setSessions(list);
    return list;
  }, []);

  useEffect(() => {
    (async () => {
      await getMe();
      const list = await refreshSessions();
      const lastId = readLastSessionId();
      const remembered = list.find((s) => s.id === lastId);
      if (remembered) {
        setActiveId(remembered.id);
      } else if (list.length > 0) {
        setActiveId(list[0].id);
      } else {
        const s = await createSession();
        setSessions([s]);
        setActiveId(s.id);
      }
      setReady(true);
    })();
  }, [refreshSessions, setActiveId]);

  const handleNew = useCallback(async () => {
    const s = await createSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
  }, [setActiveId]);

  const handleDelete = useCallback(
    async (id: string) => {
      await deleteSession(id);
      const remaining = sessions.filter((s) => s.id !== id);
      setSessions(remaining);
      if (activeId === id) {
        setActiveId(remaining[0]?.id ?? null);
      }
    },
    [sessions, activeId, setActiveId],
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
