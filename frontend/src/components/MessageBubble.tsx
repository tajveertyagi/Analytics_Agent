import { memo } from "react";
import ReactMarkdown from "react-markdown";
import type { UIMessage } from "../hooks/useChat";
import ChartRenderer from "./ChartRenderer";

function MessageBubble({ message }: { message: UIMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-3xl w-full ${isUser ? "flex justify-end" : ""}`}>
        <div
          className={
            isUser
              ? "inline-block rounded-2xl bg-amber-600 px-4 py-2 text-white"
              : "w-full rounded-2xl bg-slate-800 px-4 py-3 text-slate-100"
          }
        >
          {message.content ? (
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          ) : message.streaming ? (
            <span className="inline-flex gap-1">
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
            </span>
          ) : null}

          {message.charts.map((chart, i) => (
            <ChartRenderer key={i} figure={chart} />
          ))}
        </div>
      </div>
    </div>
  );
}

// Only the streaming assistant bubble changes token-to-token. Memoizing keeps
// every already-finished bubble (and its Plotly charts) out of the re-render
// storm that streaming would otherwise cause on the whole message list.
export default memo(MessageBubble, (a, b) => {
  const x = a.message;
  const y = b.message;
  return (
    x.id === y.id &&
    x.content === y.content &&
    x.streaming === y.streaming &&
    x.charts === y.charts
  );
});
