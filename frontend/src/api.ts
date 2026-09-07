export interface ChatSessionOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageOut {
  id: number;
  role: "user" | "assistant";
  content: string;
  charts: Record<string, unknown>[];
  created_at: string;
}

const BASE = "/api";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include", ...init });
  if (!res.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return res.json();
}

export function getMe() {
  return jsonFetch<{ user_id: string }>("/me");
}

export function listSessions() {
  return jsonFetch<ChatSessionOut[]>("/sessions");
}

export function createSession() {
  return jsonFetch<ChatSessionOut>("/sessions", { method: "POST" });
}

export function getMessages(sessionId: string) {
  return jsonFetch<ChatMessageOut[]>(`/sessions/${sessionId}/messages`);
}

export function deleteSession(sessionId: string) {
  return jsonFetch<{ ok: boolean }>(`/sessions/${sessionId}`, { method: "DELETE" });
}

export type ChatEvent =
  | { type: "token"; text: string }
  | { type: "tool_result"; tool: string; chart: Record<string, unknown> | null }
  | { type: "done"; answer: string; charts: Record<string, unknown>[] }
  | { type: "error"; message: string };

/** Sends a message and streams back SSE events, parsed frame-by-frame. */
export async function* streamMessage(sessionId: string, content: string): AsyncGenerator<ChatEvent> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`send message failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex: number;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      yield { type: event, ...parsed } as ChatEvent;
    }
  }
}
