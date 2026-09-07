from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_BYTES
from app.deps import get_db, get_owned_session
from app.document_extract import SUPPORTED_EXTENSIONS, UnsupportedFileType, extract_text
from app.models import ChatSession, UploadedFile
from app.schemas import FileOut

router = APIRouter(prefix="/api/sessions", tags=["files"])


@router.get("/{session_id}/files", response_model=list[FileOut])
def list_files(session: ChatSession = Depends(get_owned_session)):
    return session.files


@router.post("/{session_id}/files", response_model=FileOut)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

    try:
        text, truncated = extract_text(file.filename, raw)
    except UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read '{file.filename}': {e}")

    record = UploadedFile(
        session_id=session.id,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(raw),
        extracted_text=text,
        truncated=truncated,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{session_id}/files/{file_id}")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    session: ChatSession = Depends(get_owned_session),
):
    record = db.get(UploadedFile, file_id)
    if record is None or record.session_id != session.id:
        raise HTTPException(status_code=404, detail="File not found")
    db.delete(record)
    db.commit()
    return {"ok": True}
