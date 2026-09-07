import { useRef, useState, type KeyboardEvent } from "react";
import type { UploadedFileOut } from "../api";

const ACCEPT = ".csv,.xlsx,.xls,.docx,.pptx";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ChatInput({
  onSend,
  disabled,
  files,
  uploading,
  fileError,
  onUpload,
  onRemove,
}: {
  onSend: (content: string) => void;
  disabled?: boolean;
  files: UploadedFileOut[];
  uploading: boolean;
  fileError: string | null;
  onUpload: (file: File) => void;
  onRemove: (fileId: string) => void;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-slate-800 bg-slate-900 p-4">
      <div className="mx-auto max-w-3xl rounded-2xl border border-slate-700 bg-slate-800 p-2">
        {(files.length > 0 || uploading) && (
          <div className="flex flex-wrap gap-2 px-1 pb-2">
            {files.map((f) => (
              <div
                key={f.id}
                className="flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-700 px-2.5 py-1 text-xs text-slate-300"
                title={f.truncated ? "Only a preview of this file is used (it was too large to use in full)" : f.filename}
              >
                <span className="max-w-[10rem] truncate">{f.filename}</span>
                <span className="text-slate-500">{formatSize(f.size_bytes)}</span>
                {f.truncated && <span className="text-amber-500">preview only</span>}
                <button onClick={() => onRemove(f.id)} className="text-slate-500 hover:text-red-400" title="Remove">
                  ✕
                </button>
              </div>
            ))}
            {uploading && (
              <div className="flex items-center rounded-lg border border-slate-600 bg-slate-700 px-2.5 py-1 text-xs text-slate-400">
                Uploading...
              </div>
            )}
          </div>
        )}
        {fileError && <p className="px-1 pb-2 text-xs text-red-400">{fileError}</p>}
        <div className="flex items-end gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUpload(file);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            title="Attach a CSV, Excel, Word or PowerPoint file"
            className="mb-1 shrink-0 rounded-xl p-2 text-slate-400 transition hover:bg-slate-700 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M21.44 11.05l-9.19 9.19a5 5 0 01-7.07-7.07l9.19-9.19a3.5 3.5 0 014.95 4.95l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
            }}
            onKeyDown={onKeyDown}
            placeholder="Ask about transformer losses or theft cases, or an attached file..."
            rows={1}
            disabled={disabled}
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-slate-100 outline-none placeholder:text-slate-500"
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="shrink-0 rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-slate-500">
        Transformer loss data is real. Theft-case data is synthetic placeholder data.
      </p>
    </div>
  );
}
