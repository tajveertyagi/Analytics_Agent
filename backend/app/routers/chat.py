import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from plotly.utils import PlotlyJSONEncoder
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.deps import get_db, get_owned_session
from app.models import ChatMessage, ChatSession
from app.schemas import SendMessageIn
from app.data_cache import get_transformer_losses, get_theft_cases
from app.chatbot.agent import stream_ask

router = APIRouter(prefix="/api/sessions", tags=["chat"])


def _sse(event: str, data: dict) -> str:
    # Chart payloads (fig.to_dict()) can contain numpy arrays/datetime64
    # values that the stdlib json encoder can't handle -- Plotly ships its
    # own encoder that does, so use it for every SSE frame.
    return f"event: {event}\ndata: {json.dumps(data, cls=PlotlyJSONEncoder)}\n\n"


@router.post("/{session_id}/messages")
def send_message(
    body: SendMessageIn,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    question = body.content.strip()

    # Capture plain values up front -- the ORM `session` object may be
    # expired/detached once this request-scoped `db` closes, which happens
    # before the StreamingResponse body generator below actually runs.
    session_id = session.id
    history = [{"role": m.role, "content": m.content} for m in session.messages]
    is_first_message = len(history) == 0

    if not question:
        def empty_stream():
            yield _sse("error", {"message": "Empty message"})
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    db.add(ChatMessage(session_id=session_id, role="user", content=question))
    if is_first_message:
        session.title = question[:60]
    db.commit()

    losses = get_transformer_losses()
    theft = get_theft_cases()

    def event_generator():
        final_answer = ""
        final_charts: list[dict] = []
        try:
            for event in stream_ask(question, losses, theft, chat_history=history):
                if event["type"] == "token":
                    yield _sse("token", {"text": event["text"]})
                elif event["type"] == "tool_result":
                    yield _sse("tool_result", {"tool": event["tool"], "chart": event["chart"]})
                elif event["type"] == "done":
                    final_answer = event["answer"]
                    final_charts = event["charts"]
                    yield _sse("done", {"answer": final_answer, "charts": final_charts})
        except Exception as e:
            final_answer = f"Something went wrong: {e}"
            yield _sse("error", {"message": str(e)})

        write_db = SessionLocal()
        try:
            msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=final_answer,
                charts_json=json.dumps(final_charts, cls=PlotlyJSONEncoder) if final_charts else None,
            )
            write_db.add(msg)
            write_db.flush()
            write_db.query(ChatSession).filter(ChatSession.id == session_id).update(
                {"updated_at": msg.created_at}
            )
            write_db.commit()
        finally:
            write_db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
