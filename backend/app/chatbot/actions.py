"""Handlers for the assistant's *action* tools -- the ones that don't just
compute an answer but create something the user interacts with in the UI: a
downloadable report, or a draft email awaiting the user's Send click.

These are kept out of app.chatbot.tools.dispatch because (unlike the
analytics tools) they have side effects, touch the database, need the chat
session id, and must never be TTL-cached. agent.py routes ACTION_TOOLS here.

Each handler returns (content_for_llm: str, action_payload: dict). The
action payload is streamed to the frontend (SSE `tool_result.action`) and
persisted on the assistant message so the card survives a reload.
"""
import json
import re

import pandas as pd

from app import reports as R
from app.db import SessionLocal
from app.models import OutboundEmail, Report

ACTION_TOOLS = {"generate_report", "draft_report_email"}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_REPORT_KEYS = (
    "date_from",
    "date_to",
    "division",
    "feeder_name",
    "substation_name",
    "area_type",
    "dt_type",
    "title",
)


def _report_kwargs(kwargs: dict) -> dict:
    return {k: kwargs[k] for k in _REPORT_KEYS if kwargs.get(k)}


def _create_report(db, session_id: str, losses, theft, kwargs: dict) -> Report:
    filename, timeframe, filters_label, data = R.build_report(losses, theft, **_report_kwargs(kwargs))
    report = Report(
        session_id=session_id,
        filename=filename,
        timeframe_label=timeframe,
        filters_label=filters_label,
        content=data,
    )
    db.add(report)
    db.flush()
    return report


def handle_action(name: str, kwargs: dict, session_id: str, losses: pd.DataFrame, theft: pd.DataFrame):
    if session_id is None:
        return json.dumps({"error": "No chat session; cannot create a report."}), None

    db = SessionLocal()
    try:
        if name == "generate_report":
            report = _create_report(db, session_id, losses, theft, kwargs)
            db.commit()
            action = {"kind": "report", "report_id": report.id}
            content = json.dumps({
                "status": "report_ready",
                "filename": report.filename,
                "timeframe": report.timeframe_label,
                "filters": report.filters_label,
                "note": "The user now sees a download button for this .xlsx in the UI. Tell them it's ready; you cannot email it yourself.",
            })
            return content, action

        if name == "draft_report_email":
            report = _create_report(db, session_id, losses, theft, kwargs)

            raw_recipients = kwargs.get("recipients") or []
            if isinstance(raw_recipients, str):
                raw_recipients = re.split(r"[,;\s]+", raw_recipients)
            recipients = [r.strip() for r in raw_recipients if r and r.strip()]
            invalid = [r for r in recipients if not _EMAIL_RE.match(r)]
            valid = [r for r in recipients if _EMAIL_RE.match(r)]

            subject = (kwargs.get("subject") or "").strip() or f"DISCOM analytics report — {report.timeframe_label}"
            body = (kwargs.get("message") or "").strip() or (
                f"Hi,\n\nAttached is the DISCOM analytics report covering {report.timeframe_label} "
                f"(filters: {report.filters_label}).\n\nDistribution-loss figures are from real "
                f"production data; theft-case figures are synthetic placeholder data.\n\nRegards,\nSarthi"
            )

            email = OutboundEmail(
                session_id=session_id,
                report_id=report.id,
                to_addrs=",".join(valid),
                subject=subject,
                body=body,
                status="draft",
            )
            db.add(email)
            db.commit()

            action = {"kind": "email_draft", "email_id": email.id}
            content = json.dumps({
                "status": "email_draft_ready",
                "recipients": valid,
                "invalid_recipients_ignored": invalid,
                "note": (
                    "A draft email with the report attached is now shown in the UI for the user to "
                    "review. NOTHING HAS BEEN SENT. The user must check the recipients, subject and "
                    "body and click Send themselves. Do not say the email was sent; say the draft is "
                    "ready for their review" + (
                        " and ask them to add a recipient" if not valid else ""
                    ) + "."
                ),
            })
            return content, action

        return json.dumps({"error": f"Unknown action tool '{name}'"}), None
    finally:
        db.close()
