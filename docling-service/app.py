"""docling-service — document parsing microservice.

Wraps IBM DocLing to convert PDF, DOCX, PPTX, HTML, and image files
into structured Markdown + document metadata. Called by moe-codex-api
via HTTP; never exposed directly to end users.

POST /parse   — multipart file upload → parsed document
GET  /health  — liveness probe
"""
from __future__ import annotations

import logging
import os
import pathlib
import tempfile
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

app = FastAPI(title="moe-docling", version="1.0.0")

# Initialise converter once at startup (loads ML models into memory)
try:
    from docling.document_converter import DocumentConverter
    _converter = DocumentConverter()
    _docling_available = True
except Exception as _e:
    logger.warning("DocLing unavailable: %s", _e)
    _converter = None
    _docling_available = False

_SUPPORTED_SUFFIXES = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm",
                       ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "moe-docling",
        "docling_available": _docling_available,
    }


@app.post("/parse")
async def parse_document(file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse an uploaded document and return Markdown text + metadata."""
    if not _docling_available:
        raise HTTPException(status_code=503, detail="DocLing not available")

    filename = file.filename or "document"
    suffix = pathlib.Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {suffix!r}. Supported: {sorted(_SUPPORTED_SUFFIXES)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = _converter.convert(tmp_path)
        doc = result.document

        markdown = doc.export_to_markdown()
        page_count = len(doc.pages) if hasattr(doc, "pages") and doc.pages else None

        # Extract top-level headings as section titles
        sections: list[str] = []
        try:
            for item in doc.iterate_items():
                from docling_core.types.doc import TextItem, DocItemLabel
                if hasattr(item, "label") and item.label == DocItemLabel.SECTION_HEADER:
                    sections.append(item.text)
        except Exception:
            pass

        return {
            "filename": filename,
            "title": sections[0] if sections else pathlib.Path(filename).stem,
            "markdown": markdown,
            "page_count": page_count,
            "sections": sections[:20],  # cap to first 20 headings
            "char_count": len(markdown),
            "byte_size": len(content),
        }
    except Exception as exc:
        logger.exception("DocLing conversion failed for %s", filename)
        return JSONResponse(
            status_code=500,
            content={"error": f"Conversion failed: {exc}"},
        )
    finally:
        try:
            pathlib.Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass
