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
    created_at: datetime

    class Config:
        from_attributes = True


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
