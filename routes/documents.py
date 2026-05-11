"""routes/documents.py — Document Intelligence API endpoints.

POST /v1/codex/documents/parse     — upload file → parsed Markdown + metadata
POST /v1/codex/documents/ingest    — upload file → parse → ingest into sovereign graph
POST /v1/codex/documents/describe  — upload page image → ColPali-style visual description
GET  /v1/codex/documents/health    — DocLing service reachability
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from services.documents import (
    parse_document,
    ingest_to_graph,
    visual_describe,
    health_check,
    DOCLING_ENABLED,
    DOCLING_URL,
)

router = APIRouter(prefix="/v1/codex/documents")

_IMAGE_MIMES = {"image/png", "image/jpeg", "image/tiff", "image/bmp", "image/webp"}


@router.get("/health")
async def documents_health():
    ok = await health_check()
    return {
        "docling_reachable": ok,
        "docling_enabled":   DOCLING_ENABLED,
        "docling_url":       DOCLING_URL,
    }


@router.post("/parse")
async def documents_parse(file: UploadFile = File(...)):
    """Parse an uploaded document. Returns Markdown text + document metadata.

    Supported formats: PDF, DOCX, PPTX, XLSX, HTML, PNG, JPG, TIFF.
    """
    if not DOCLING_ENABLED:
        return JSONResponse(status_code=503,
                            content={"error": "Document Intelligence is disabled"})

    content = await file.read()
    if not content:
        return JSONResponse(status_code=400, content={"error": "Empty file"})

    result = await parse_document(file.filename or "document", content)
    if "error" in result:
        return JSONResponse(status_code=502, content=result)
    return result


@router.post("/ingest")
async def documents_ingest(
    file: UploadFile = File(...),
    source_tag: str = Form(default="moe-codex-documents"),
    trust_floor: float = Form(default=0.6),
):
    """Parse a document and ingest its text into the moe-sovereign knowledge graph.

    The parsed Markdown is chunked and imported via /graph/knowledge/import so
    the GraphRAG layer can retrieve it in future queries.
    """
    if not DOCLING_ENABLED:
        return JSONResponse(status_code=503,
                            content={"error": "Document Intelligence is disabled"})

    content = await file.read()
    if not content:
        return JSONResponse(status_code=400, content={"error": "Empty file"})

    parsed = await parse_document(file.filename or "document", content)
    if "error" in parsed:
        return JSONResponse(status_code=502, content=parsed)

    ingest_result = await ingest_to_graph(parsed, source_tag=source_tag,
                                          trust_floor=trust_floor)
    if "error" in ingest_result:
        return JSONResponse(status_code=502, content={"parse": parsed, **ingest_result})

    return {
        "parse":  {k: v for k, v in parsed.items() if k != "markdown"},
        "ingest": ingest_result,
    }


@router.post("/describe")
async def documents_describe(
    file: UploadFile = File(...),
    question: str = Form(default="Describe the content of this document page."),
):
    """Describe a document page image using the moe-sovereign vision endpoint.

    Implements the ColPali-style visual document understanding path: send a page
    image to the vision_expert model for semantic description. Useful for
    scan-heavy PDFs where text extraction yields poor results.
    """
    content = await file.read()
    if not content:
        return JSONResponse(status_code=400, content={"error": "Empty file"})

    content_type = file.content_type or ""
    if content_type not in _IMAGE_MIMES:
        # Accept by filename suffix as fallback
        fn = (file.filename or "").lower()
        if not any(fn.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")):
            return JSONResponse(
                status_code=415,
                content={"error": f"Expected an image file, got: {content_type!r}"},
            )

    description = await visual_describe(content, filename=file.filename or "page.png",
                                        question=question)
    if description.startswith("Error:"):
        return JSONResponse(status_code=502, content={"error": description})

    return {
        "filename":    file.filename,
        "question":    question,
        "description": description,
    }
