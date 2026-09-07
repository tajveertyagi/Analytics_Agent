"""Extracts a bounded, LLM-friendly text preview from an uploaded document
(CSV, Excel, Word, PowerPoint) so the chatbot can answer questions about it
directly from that content -- no code execution against the file, just text
extraction. Spreadsheets get column info + numeric summary stats + a row
preview (rather than the full sheet) to keep the prompt bounded; very large
documents of any type are truncated with a note so the model doesn't treat a
partial view as the whole document.
"""
import io
import os

import pandas as pd

MAX_CHARS = 18000
PREVIEW_ROWS = 50

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".docx", ".pptx"}


class UnsupportedFileType(ValueError):
    pass


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_CHARS:
        return text, False
    return text[:MAX_CHARS] + "\n\n[... truncated, rest of document not shown ...]", True


def _describe_frame(name: str, df: pd.DataFrame) -> str:
    parts = [
        f"### {name}",
        f"{len(df)} rows x {len(df.columns)} columns.",
        f"Columns: {', '.join(str(c) for c in df.columns)}",
    ]
    numeric_cols = df.select_dtypes("number").columns
    if len(numeric_cols) > 0:
        parts.append("Numeric summary:\n" + df[numeric_cols].describe().round(2).to_string())
    parts.append(f"First {min(PREVIEW_ROWS, len(df))} rows:\n" + df.head(PREVIEW_ROWS).to_string(index=False))
    return "\n\n".join(parts)


def _extract_csv(raw: bytes) -> str:
    df = pd.read_csv(io.BytesIO(raw))
    return _describe_frame("Data", df)


def _extract_excel(raw: bytes) -> str:
    sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None)
    return "\n\n".join(_describe_frame(name, df) for name, df in sheets.items())


def _extract_docx(raw: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(raw))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _extract_pptx(raw: bytes) -> str:
    from pptx import Presentation

    prs = Presentation(io.BytesIO(raw))
    parts = []
    for i, slide in enumerate(prs.slides, start=1):
        texts = [
            shape.text_frame.text.strip()
            for shape in slide.shapes
            if shape.has_text_frame and shape.text_frame.text.strip()
        ]
        if texts:
            parts.append(f"--- Slide {i} ---\n" + "\n".join(texts))
    return "\n\n".join(parts)


def extract_text(filename: str, raw: bytes) -> tuple[str, dict]:
    """Returns (bounded text preview, {"truncated": bool})."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".csv":
        text = _extract_csv(raw)
    elif ext in (".xlsx", ".xls"):
        text = _extract_excel(raw)
    elif ext == ".docx":
        text = _extract_docx(raw)
    elif ext == ".pptx":
        text = _extract_pptx(raw)
    else:
        raise UnsupportedFileType(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if not text.strip():
        return "[No extractable text found in this document.]", False

    return _truncate(text)
