import { useCallback, useEffect, useState } from "react";
import { getMessages, streamMessage, type ChatMessageOut } from "../api";

export interface UIMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  charts: Record<string, unknown>[];
  streaming?: boolean;
}

function fromServer(m: ChatMessageOut): UIMessage {
  return { id: String(m.id), role: m.role, content: m.content, charts: m.charts };
}

// While the browser tab is occluded (presenting on another display, screen
// mirror, minimized) it pauses rAF and throttles timers, but the SSE fetch
// keeps buffering. On un-occlude the whole backlog arrives at once. Applying
// one setState per buffered token there means dozens of full re-renders +
// markdown re-parses back to back -- the "hang". Coalescing tokens on a short
// interval bounds that to a handful of renders regardless of arrival rate.
const TOKEN_FLUSH_MS = 60;

export function useChat(sessionId: string | null, onFirstMessage?: () => void) {
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    getMessages(sessionId).then((msgs) => {
      if (!cancelled) setMessages(msgs.map(fromServer));
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const updateLastAssistant = useCallback((updater: (m: UIMessage) => UIMessage) => {
    setMessages((prev) => {
      const lastIdx = prev.length - 1;
      if (lastIdx < 0 || prev[lastIdx].role !== "assistant") return prev;
      const next = [...prev];
      next[lastIdx] = updater(next[lastIdx]);
      return next;
    });
  }, []);

  const send = useCallback(
    async (content: string) => {
      if (!sessionId || sending) return;
      const wasEmpty = messages.length === 0;
      setMessages((prev) => [
        ...prev,
        { id: `tmp-u-${Date.now()}`, role: "user", content, charts: [] },
        { id: `tmp-a-${Date.now()}`, role: "assistant", content: "", charts: [], streaming: true },
      ]);
      setSending(true);

      // Token coalescing: accumulate incoming text, flush to state on a timer.
      let pending = "";
      let timer: ReturnType<typeof setTimeout> | null = null;
      const flush = () => {
        timer = null;
        if (!pending) return;
        const chunk = pending;
        pending = "";
        updateLastAssistant((m) => ({ ...m, content: m.content + chunk }));
      };

      try {
        for await (const event of streamMessage(sessionId, content)) {
          if (event.type === "token") {
            pending += event.text;
            if (timer == null) timer = setTimeout(flush, TOKEN_FLUSH_MS);
          } else if (event.type === "tool_result") {
            if (event.chart) {
              flush();
              updateLastAssistant((m) => ({ ...m, charts: [...m.charts, event.chart!] }));
            }
          } else if (event.type === "done") {
            if (timer != null) clearTimeout(timer);
            pending = "";
            updateLastAssistant((m) => ({ ...m, content: event.answer, streaming: false }));
          } else if (event.type === "error") {
            if (timer != null) clearTimeout(timer);
            pending = "";
            updateLastAssistant((m) => ({ ...m, content: `⚠️ ${event.message}`, streaming: false }));
          }
        }
        if (timer != null) {
          clearTimeout(timer);
          flush();
        }
        if (wasEmpty) onFirstMessage?.();
      } catch (e) {
        if (timer != null) clearTimeout(timer);
        updateLastAssistant((m) => ({ ...m, content: `⚠️ ${(e as Error).message}`, streaming: false }));
      } finally {
        setSending(false);
      }
    },
    [sessionId, sending, messages.length, updateLastAssistant, onFirstMessage],
  );

  return { messages, send, sending };
}
