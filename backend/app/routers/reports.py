"""Endpoints backing the report-download button and the email review card
that the assistant's generate_report / draft_report_email tools put in the
chat. Nothing here sends an email except POST .../send, which the user
triggers by clicking Send on the reviewed draft (human-in-the-loop)."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.deps import get_db, get_owned_session
from app.mailer import MailNotConfigured, send_email
from app.models import ChatSession, OutboundEmail, Report
from app.schemas import EmailUpdateIn, OutboundEmailOut, ReportMetaOut

router = APIRouter(prefix="/api/sessions", tags=["reports"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_report(db: Session, session: ChatSession, report_id: str) -> Report:
    report = db.get(Report, report_id)
    if report is None or report.session_id != session.id:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


def _get_email(db: Session, session: ChatSession, email_id: str) -> OutboundEmail:
    email = db.get(OutboundEmail, email_id)
    if email is None or email.session_id != session.id:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


def _report_meta(session_id: str, report: Report) -> ReportMetaOut:
    return ReportMetaOut(
        id=report.id,
        filename=report.filename,
        timeframe_label=report.timeframe_label,
        filters_label=report.filters_label,
        download_url=f"/api/sessions/{session_id}/reports/{report.id}/download",
        created_at=report.created_at,
    )


def _email_out(session_id: str, email: OutboundEmail) -> OutboundEmailOut:
    return OutboundEmailOut(
        id=email.id,
        to=[a for a in email.to_addrs.split(",") if a],
        subject=email.subject,
        body=email.body,
        status=email.status,
        error=email.error,
        created_at=email.created_at,
        sent_at=email.sent_at,
        report=_report_meta(session_id, email.report) if email.report else None,
    )


@router.get("/{session_id}/reports/{report_id}", response_model=ReportMetaOut)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    return _report_meta(session.id, _get_report(db, session, report_id))


@router.get("/{session_id}/reports/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    report = _get_report(db, session, report_id)
    return Response(
        content=report.content,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{report.filename}"'},
    )


@router.get("/{session_id}/emails/{email_id}", response_model=OutboundEmailOut)
def get_email(
    email_id: str,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    return _email_out(session.id, _get_email(db, session, email_id))


@router.patch("/{session_id}/emails/{email_id}", response_model=OutboundEmailOut)
def update_email(
    email_id: str,
    body: EmailUpdateIn,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    email = _get_email(db, session, email_id)
    if email.status != "draft":
        raise HTTPException(status_code=409, detail=f"Email is already {email.status}")
    if body.to is not None:
        email.to_addrs = ",".join(a.strip() for a in body.to if a and a.strip())
    if body.subject is not None:
        email.subject = body.subject
    if body.body is not None:
        email.body = body.body
    db.commit()
    db.refresh(email)
    return _email_out(session.id, email)


@router.post("/{session_id}/emails/{email_id}/send", response_model=OutboundEmailOut)
def send_drafted_email(
    email_id: str,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    email = _get_email(db, session, email_id)
    if email.status != "draft":
        raise HTTPException(status_code=409, detail=f"Email is already {email.status}")

    recipients = [a for a in email.to_addrs.split(",") if a]
    if not recipients:
        raise HTTPException(status_code=400, detail="Add at least one recipient before sending.")
    bad = [a for a in recipients if not _EMAIL_RE.match(a)]
    if bad:
        raise HTTPException(status_code=400, detail=f"Not a valid email address: {', '.join(bad)}")

    report = email.report
    attachment = (report.filename, report.content) if report else None

    try:
        send_email(recipients, email.subject, email.body, attachment)
    except MailNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # SMTP failure -- keep the draft so the user can retry
        email.error = str(e)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Could not send: {e}")

    email.status = "sent"
    email.sent_at = datetime.now(timezone.utc)
    email.error = None
    db.commit()
    db.refresh(email)
    return _email_out(session.id, email)


@router.post("/{session_id}/emails/{email_id}/cancel", response_model=OutboundEmailOut)
def cancel_drafted_email(
    email_id: str,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    email = _get_email(db, session, email_id)
    if email.status == "sent":
        raise HTTPException(status_code=409, detail="Email was already sent")
    email.status = "cancelled"
    db.commit()
    db.refresh(email)
    return _email_out(session.id, email)
