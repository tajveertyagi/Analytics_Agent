import { useEffect, useState } from "react";
import { getReport, type ReportMeta } from "../api";

export default function ReportCard({ sessionId, reportId }: { sessionId: string; reportId: string }) {
  const [meta, setMeta] = useState<ReportMeta | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getReport(sessionId, reportId)
      .then((m) => !cancelled && setMeta(m))
      .catch((e) => !cancelled && setError((e as Error).message));
    return () => {
      cancelled = true;
    };
  }, [sessionId, reportId]);

  if (error) {
    return <div className="my-2 rounded-lg border border-red-800 bg-red-950/40 p-3 text-xs text-red-300">Report unavailable: {error}</div>;
  }
  if (!meta) {
    return <div className="my-2 rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-500">Preparing report…</div>;
  }

  return (
    <div className="my-2 rounded-lg border border-slate-700 bg-slate-900 p-3">
      <div className="flex items-center gap-3">
        <svg className="h-8 w-8 shrink-0 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6M8 13h8M8 17h8M8 9h2" />
        </svg>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-200">{meta.filename}</p>
          <p className="text-xs text-slate-500">
            Excel report · {meta.timeframe_label}
            {meta.filters_label && meta.filters_label !== "none (whole network)" ? ` · ${meta.filters_label}` : ""}
          </p>
        </div>
        <a
          href={meta.download_url}
          download={meta.filename}
          className="shrink-0 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-amber-500"
        >
          Download
        </a>
      </div>
    </div>
  );
}
