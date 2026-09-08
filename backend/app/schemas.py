from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    charts: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ReportMetaOut(BaseModel):
    id: str
    filename: str
    timeframe_label: str
    filters_label: str
    download_url: str
    created_at: datetime


class OutboundEmailOut(BaseModel):
    id: str
    to: list[str]
    subject: str
    body: str
    status: str
    error: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    report: Optional[ReportMetaOut] = None


class EmailUpdateIn(BaseModel):
    to: Optional[list[str]] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class SendMessageIn(BaseModel):
    content: str


class MeOut(BaseModel):
    user_id: str


class FileOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    truncated: bool
    created_at: datetime

    class Config:
        from_attributes = True
