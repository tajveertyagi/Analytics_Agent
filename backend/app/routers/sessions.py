import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user_id, get_owned_session
from app.models import ChatSession, ChatMessage
from app.schemas import SessionOut, MessageOut

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
    return db.scalars(stmt).all()


@router.post("", response_model=SessionOut)
def create_session(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    session = ChatSession(user_id=user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def get_messages(db: Session = Depends(get_db), session: ChatSession = Depends(get_owned_session)):
    out = []
    for m in session.messages:
        out.append(MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            charts=json.loads(m.charts_json) if m.charts_json else [],
            actions=json.loads(m.actions_json) if m.actions_json else [],
            created_at=m.created_at,
        ))
    return out


@router.delete("/{session_id}")
def delete_session(db: Session = Depends(get_db), session: ChatSession = Depends(get_owned_session)):
    db.delete(session)
    db.commit()
    return {"ok": True}
