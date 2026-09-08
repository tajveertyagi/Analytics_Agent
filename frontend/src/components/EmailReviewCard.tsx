import { useEffect, useState } from "react";
import { cancelEmail, getEmail, sendEmail, updateEmail, type OutboundEmail } from "../api";

// Human-in-the-loop: the assistant only ever DRAFTS a report email. This card
// lets the user check and edit recipients / subject / body and is the only
// place a send actually happens -- clicking Send.
export default function EmailReviewCard({ sessionId, emailId }: { sessionId: string; emailId: string }) {
  const [email, setEmail] = useState<OutboundEmail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState<null | "send" | "cancel">(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEmail(sessionId, emailId)
      .then((e) => {
        if (cancelled) return;
        setEmail(e);
        setTo(e.to.join(", "));
        setSubject(e.subject);
        setBody(e.body);
      })
      .catch((e) => !cancelled && setLoadError((e as Error).message));
    return () => {
      cancelled = true;
    };
  }, [sessionId, emailId]);

  if (loadError) {
    return <div className="my-2 rounded-lg border border-red-800 bg-red-950/40 p-3 text-xs text-red-300">Email draft unavailable: {loadError}</div>;
  }
  if (!email) {
    return <div className="my-2 rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-500">Preparing draft…</div>;
  }

  const parseTo = (raw: string) => raw.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);

  const persist = async () => {
    try {
      const updated = await updateEmail(sessionId, emailId, { to: parseTo(to), subject, body });
      setEmail(updated);
    } catch {
      // non-fatal; Send re-persists and surfaces any real error
    }
  };

  const doSend = async () => {
    setBusy("send");
    setActionError(null);
    try {
      await updateEmail(sessionId, emailId, { to: parseTo(to), subject, body });
      const sent = await sendEmail(sessionId, emailId);
      setEmail(sent);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const doCancel = async () => {
    setBusy("cancel");
    setActionError(null);
    try {
      setEmail(await cancelEmail(sessionId, emailId));
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (email.status === "sent") {
    return (
      <div className="my-2 rounded-lg border border-emerald-800 bg-emerald-950/30 p-3 text-xs text-emerald-300">
        ✓ Email sent to {email.to.join(", ")}
        {email.sent_at ? ` on ${new Date(email.sent_at).toLocaleString()}` : ""}.
        {email.report ? ` Attached: ${email.report.filename}.` : ""}
      </div>
    );
  }

  if (email.status === "cancelled") {
    return (
      <div className="my-2 rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-500">
        Draft cancelled — nothing was sent.
      </div>
    );
  }

  const inputCls =
    "w-full rounded-md border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-sm text-slate-100 outline-none focus:border-amber-600";

  return (
    <div className="my-2 rounded-lg border border-amber-800/60 bg-slate-900 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-amber-500">
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="2" y="4" width="20" height="16" rx="2" />
          <path d="m22 7-10 5L2 7" />
        </svg>
        Review this draft — it won&apos;t send until you click Send
      </div>

      <div className="space-y-2">
        <label className="block">
          <span className="text-xs text-slate-500">To (comma-separated)</span>
          <input
            className={inputCls}
            value={to}
            placeholder="name@discom.in"
            onChange={(e) => setTo(e.target.value)}
            onBlur={persist}
          />
        </label>
        <label className="block">
          <span className="text-xs text-slate-500">Subject</span>
          <input className={inputCls} value={subject} onChange={(e) => setSubject(e.target.value)} onBlur={persist} />
        </label>
        <label className="block">
          <span className="text-xs text-slate-500">Message</span>
          <textarea
            className={`${inputCls} min-h-[90px] resize-y`}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onBlur={persist}
          />
        </label>
        {email.report && (
          <p className="text-xs text-slate-500">
            Attachment:{" "}
            <a href={email.report.download_url} download={email.report.filename} className="text-amber-500 hover:underline">
              {email.report.filename}
            </a>
          </p>
        )}
      </div>

      {(actionError || email.error) && (
        <p className="mt-2 text-xs text-red-400">{actionError ?? email.error}</p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          onClick={doSend}
          disabled={busy !== null || parseTo(to).length === 0}
          className="rounded-lg bg-amber-600 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-amber-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy === "send" ? "Sending…" : "Send"}
        </button>
        <button
          onClick={doCancel}
          disabled={busy !== null}
          className="rounded-lg border border-slate-700 px-4 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-slate-800 disabled:opacity-40"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
