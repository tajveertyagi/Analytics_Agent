export interface ChatSessionOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export type ChatAction =
  | { kind: "report"; report_id: string }
  | { kind: "email_draft"; email_id: string };

export interface ChatMessageOut {
  id: number;
  role: "user" | "assistant";
  content: string;
  charts: Record<string, unknown>[];
  actions: ChatAction[];
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

export interface UploadedFileOut {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  truncated: boolean;
  created_at: string;
}

export function listFiles(sessionId: string) {
  return jsonFetch<UploadedFileOut[]>(`/sessions/${sessionId}/files`);
}

export async function uploadFile(sessionId: string, file: File): Promise<UploadedFileOut> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/sessions/${sessionId}/files`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `upload failed: ${res.status}`);
  }
  return res.json();
}

export function deleteFile(sessionId: string, fileId: string) {
  return jsonFetch<{ ok: boolean }>(`/sessions/${sessionId}/files/${fileId}`, { method: "DELETE" });
}

export interface ReportMeta {
  id: string;
  filename: string;
  timeframe_label: string;
  filters_label: string;
  download_url: string;
  created_at: string;
}

export interface OutboundEmail {
  id: string;
  to: string[];
  subject: string;
  body: string;
  status: "draft" | "sent" | "cancelled";
  error: string | null;
  created_at: string;
  sent_at: string | null;
  report: ReportMeta | null;
}

export function getReport(sessionId: string, reportId: string) {
  return jsonFetch<ReportMeta>(`/sessions/${sessionId}/reports/${reportId}`);
}

export function getEmail(sessionId: string, emailId: string) {
  return jsonFetch<OutboundEmail>(`/sessions/${sessionId}/emails/${emailId}`);
}

export function updateEmail(
  sessionId: string,
  emailId: string,
  patch: { to?: string[]; subject?: string; body?: string },
) {
  return jsonFetch<OutboundEmail>(`/sessions/${sessionId}/emails/${emailId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function sendEmail(sessionId: string, emailId: string): Promise<OutboundEmail> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/emails/${emailId}/send`, {
    method: "POST",
    credentials: "include",
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail ?? `send failed: ${res.status}`);
  return data as OutboundEmail;
}

export function cancelEmail(sessionId: string, emailId: string) {
  return jsonFetch<OutboundEmail>(`/sessions/${sessionId}/emails/${emailId}/cancel`, { method: "POST" });
}

export type ChatEvent =
  | { type: "token"; text: string }
  | { type: "tool_result"; tool: string; chart: Record<string, unknown> | null; action: ChatAction | null }
  | { type: "done"; answer: string; charts: Record<string, unknown>[]; actions: ChatAction[] }
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
