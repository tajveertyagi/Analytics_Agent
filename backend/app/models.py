import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(default="New chat")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id"
    )
    files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="UploadedFile.created_at"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Report.created_at"
    )
    emails: Mapped[list["OutboundEmail"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="OutboundEmail.created_at"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column()  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    charts_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of Plotly figure dicts
    actions_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of UI action cards (report / email draft)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    filename: Mapped[str] = mapped_column()
    content_type: Mapped[str] = mapped_column()
    size_bytes: Mapped[int] = mapped_column()
    extracted_text: Mapped[str] = mapped_column(Text)  # bounded preview fed to the LLM as context
    truncated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    session: Mapped["ChatSession"] = relationship(back_populates="files")


class Report(Base):
    """A generated multi-sheet Excel analytics report, kept so the user can
    download it (or re-download it after a page reload) and so a drafted
    email has something to attach. The .xlsx bytes live in the row."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    filename: Mapped[str] = mapped_column()
    timeframe_label: Mapped[str] = mapped_column()
    filters_label: Mapped[str] = mapped_column(default="none (whole network)")
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    session: Mapped["ChatSession"] = relationship(back_populates="reports")


class OutboundEmail(Base):
    """A report email the assistant drafted. It stays in status 'draft' -- and
    sends nothing -- until the user reviews it in the UI and clicks Send
    (human-in-the-loop), which flips it to 'sent'; Cancel flips it to
    'cancelled'."""

    __tablename__ = "outbound_emails"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    to_addrs: Mapped[str] = mapped_column(default="")  # comma-separated
    subject: Mapped[str] = mapped_column(default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(default="draft")  # "draft" | "sent" | "cancelled"
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    session: Mapped["ChatSession"] = relationship(back_populates="emails")
    report: Mapped["Report | None"] = relationship()
