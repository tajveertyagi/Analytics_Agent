import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { useChat } from "../hooks/useChat";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

export default function ChatWindow({
  sessionId,
  onFirstMessage,
}: {
  sessionId: string | null;
  onFirstMessage?: () => void;
}) {
  const { messages, send, sending } = useChat(sessionId, onFirstMessage);
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  // Stick to the bottom only while the user hasn't scrolled up to read history.
  const pinnedToBottom = useRef(true);
  const lateScroll = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Direct scrollTop write -- no rAF, no scrollIntoView animation. rAF is
  // frozen while the tab is occluded (presenting on a second display, screen
  // mirror), and a fresh "smooth" animation per update piles up when the main
  // thread is busy, which is what made the list lurch / appear out of order.
  const scrollToBottom = useCallback(() => {
    if (!pinnedToBottom.current) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    pinnedToBottom.current = distanceFromBottom < 120;
  }, []);

  // Runs synchronously after every render that changed the message list --
  // including in a hidden tab, unlike rAF / ResizeObserver / paint callbacks.
  useLayoutEffect(() => {
    scrollToBottom();
    // Charts (Plotly) mount a frame or two later and add height; catch that.
    if (lateScroll.current != null) clearTimeout(lateScroll.current);
    lateScroll.current = setTimeout(scrollToBottom, 80);
  }, [messages, scrollToBottom]);

  // Window / display resize reflows the transcript while it's on screen.
  useEffect(() => {
    const node = contentRef.current;
    if (!node) return;
    const ro = new ResizeObserver(() => scrollToBottom());
    ro.observe(node);
    return () => ro.disconnect();
  }, [scrollToBottom]);

  // Coming back from an occluded state is when a backlog of streamed content
  // has just landed; do one settle pass instead of replaying queued scrolls.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") scrollToBottom();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [scrollToBottom]);

  // New session: start pinned to the bottom again.
  useEffect(() => {
    pinnedToBottom.current = true;
  }, [sessionId]);

  useEffect(
    () => () => {
      if (lateScroll.current != null) clearTimeout(lateScroll.current);
    },
    [],
  );

  if (!sessionId) {
    return (
      <div className="flex h-full flex-1 items-center justify-center text-slate-500">
        Select a chat or start a new one.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 flex-col">
      <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto px-4 py-6">
        <div ref={contentRef} className="mx-auto max-w-3xl">
          {messages.length === 0 && (
            <div className="mt-20 text-center text-slate-500">
              <p className="text-lg font-medium text-slate-300">Ask about the DISCOM data</p>
              <p className="mt-1 text-sm">
                e.g. "Which division has the highest average distribution loss?"
              </p>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
        </div>
      </div>
      <ChatInput onSend={send} disabled={sending} />
    </div>
  );
}
