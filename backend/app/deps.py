from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import USER_COOKIE_NAME
from app.db import SessionLocal
from app.models import ChatSession, User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id(
    response: Response,
    db: Session = Depends(get_db),
    vidyutiq_uid: str | None = Cookie(default=None),
) -> str:
    """Anonymous per-browser identity: reads the uid cookie, or creates a new
    user + cookie on first visit. No login -- mirrors ChatGPT's guest mode."""
    if vidyutiq_uid:
        user = db.get(User, vidyutiq_uid)
        if user:
            return user.id

    user = User()
    db.add(user)
    db.commit()
    db.refresh(user)

    response.set_cookie(
        key=USER_COOKIE_NAME,
        value=user.id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
    )
    return user.id


def get_owned_session(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
