"""services/documents.py — Document Intelligence client.

Connects moe-codex to two capabilities:
  1. DocLing (moe-docling container) — parses PDF/DOCX/PPTX/images to Markdown.
  2. ColPali-style visual description — sends document page images to moe-sovereign's
     vision endpoint for semantic understanding of scan-heavy documents.

After parsing, callers can push extracted text into the moe-sovereign knowledge graph
via the existing sovereign_client.knowledge_import() path.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx

from services.sovereign_client import knowledge_import  # noqa: E402 (after env-var setup)

logger = logging.getLogger(__name__)

DOCLING_URL     = os.getenv("DOCLING_URL",     "http://moe-docling:7080")
DOCLING_ENABLED = os.getenv("DOCLING_ENABLED", "true").lower() not in ("0", "false", "no")
DOCLING_TIMEOUT = float(os.getenv("DOCLING_TIMEOUT", "120"))

SOVEREIGN_URL     = os.getenv("SOVEREIGN_URL",     "http://moe-sovereign:8002")
SOVEREIGN_API_KEY = os.getenv("SOVEREIGN_API_KEY", "")
VISION_MODEL      = os.getenv("VISION_MODEL",      "vision_expert")

# Maximum characters of parsed Markdown sent to the graph in a single import.
# Sovereign's knowledge import endpoint has a payload limit; we chunk large docs.
_CHUNK_SIZE = int(os.getenv("DOC_CHUNK_CHARS", "4000"))


def _sovereign_headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if SOVEREIGN_API_KEY:
        h["Authorization"] = f"Bearer {SOVEREIGN_API_KEY}"
    return h


async def parse_document(filename: str, file_bytes: bytes) -> dict[str, Any]:
    """Upload a file to the DocLing service and return the parsed result.

    Returns a dict with keys: filename, title, markdown, page_count, sections,
    char_count, byte_size — or {"error": ...} on failure.
    """
    if not DOCLING_ENABLED:
        return {"error": "Document Intelligence is not enabled (DOCLING_ENABLED=false)"}
    try:
        async with httpx.AsyncClient(timeout=DOCLING_TIMEOUT) as c:
            r = await c.post(
                f"{DOCLING_URL}/parse",
                files={"file": (filename, file_bytes)},
            )
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"DocLing HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        return {"error": str(exc)}


def _chunk_text(text: str, size: int) -> list[str]:
    """Split text into chunks of at most `size` characters at paragraph boundaries."""
    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > size and current:
            chunks.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:size]]


async def ingest_to_graph(
    parsed: dict[str, Any],
    source_tag: str = "moe-codex-documents",
    trust_floor: float = 0.6,
) -> dict[str, Any]:
    """Ingest a parsed document into the moe-sovereign knowledge graph.

    Chunks the Markdown into ≤_CHUNK_SIZE segments and imports each as a
    knowledge bundle entity so the GraphRAG layer can index and retrieve it.

    Returns the last import result, or {"error": ...} on failure.
    """
    markdown = parsed.get("markdown", "")
    title = parsed.get("title", parsed.get("filename", "document"))
    if not markdown:
        return {"error": "No markdown content to ingest"}

    chunks = _chunk_text(markdown, _CHUNK_SIZE)
    last_result: dict[str, Any] = {}

    for i, chunk in enumerate(chunks):
        bundle = {
            "@type": "DocumentChunk",
            "title": f"{title} (chunk {i + 1}/{len(chunks)})",
            "content": chunk,
            "source_filename": parsed.get("filename", ""),
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        try:
            last_result = await knowledge_import(bundle, source_tag=source_tag,
                                                 trust_floor=trust_floor)
        except Exception as exc:
            return {"error": f"Graph import failed at chunk {i}: {exc}"}

    return {
        "ingested_chunks": len(chunks),
        "title": title,
        "last_import": last_result,
    }


async def visual_describe(image_bytes: bytes, filename: str = "page.png",
                          question: str = "Describe the content of this document page.") -> str:
    """Describe a document page image using moe-sovereign's vision endpoint.

    This is the ColPali-style path: rather than embedding pages with PaliGemma
    locally (requires a 6 GB model), we delegate visual understanding to the
    vision_expert in moe-sovereign which runs on the inference nodes.

    Returns a descriptive text string, or an error message prefixed with 'Error:'.
    """
    b64 = base64.b64encode(image_bytes).decode()
    mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                f"{SOVEREIGN_URL}/v1/chat/completions",
                json={
                    "model": VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url",
                                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                                {"type": "text", "text": question},
                            ],
                        }
                    ],
                    "max_tokens": 512,
                },
                headers=_sovereign_headers(),
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("Visual describe failed: %s", exc)
        return f"Error: {exc}"


async def health_check() -> bool:
    if not DOCLING_ENABLED:
        return True
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{DOCLING_URL}/health")
            return r.status_code == 200
    except Exception:
        return False
