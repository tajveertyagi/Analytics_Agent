import type { ChatSessionOut } from "../api";

export default function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: {
  sessions: ChatSessionOut[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="flex h-full w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950">
      <div className="p-3">
        <div className="mb-3 flex items-center gap-2 px-1">
          <svg
            className="h-6 w-6 text-orange-500"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="4" y="8" width="16" height="11" rx="3" />
            <path d="M12 8V4" />
            <circle cx="12" cy="3" r="1.4" fill="currentColor" />
            <path d="M4 12H2M22 12h-2" />
            <circle cx="9" cy="13.5" r="1.4" fill="currentColor" stroke="none" />
            <circle cx="15" cy="13.5" r="1.4" fill="currentColor" stroke="none" />
            <path d="M9.5 16.5h5" />
          </svg>
          <span className="font-semibold text-slate-100">Sarthi</span>
        </div>
        <button
          onClick={onNew}
          className="w-full rounded-lg border border-slate-700 px-3 py-2 text-left text-sm font-medium text-slate-200 transition hover:bg-slate-800"
        >
          + New chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2">
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`group mb-1 flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition ${
              s.id === activeId ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:bg-slate-900"
            }`}
          >
            <span className="truncate">{s.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(s.id);
              }}
              className="ml-2 hidden shrink-0 text-slate-500 hover:text-red-400 group-hover:block"
              title="Delete chat"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-800 p-3 text-xs text-slate-500">
        Anonymous session · this browser only
      </div>
    </div>
  );
}
