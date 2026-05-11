"""tests/test_documents.py — Unit tests for services/documents.py and routes/documents.py."""
from __future__ import annotations

import base64
import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from services.documents import (
    parse_document,
    ingest_to_graph,
    visual_describe,
    health_check,
    DOCLING_URL,
    SOVEREIGN_URL,
    _chunk_text,
)


# ─── _chunk_text ──────────────────────────────────────────────────────────────

def test_chunk_text_single_chunk():
    text = "Hello world"
    chunks = _chunk_text(text, size=100)
    assert chunks == ["Hello world"]


def test_chunk_text_splits_at_paragraph():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = _chunk_text(text, size=30)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 60  # generous bound due to boundary splitting


def test_chunk_text_empty_falls_back():
    chunks = _chunk_text("", size=100)
    assert chunks == [""]


def test_chunk_text_no_split_when_fits():
    text = "Short text\n\nSmall paragraph."
    chunks = _chunk_text(text, size=1000)
    assert len(chunks) == 1


# ─── parse_document ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_parse_document_success():
    respx.post(f"{DOCLING_URL}/parse").mock(return_value=httpx.Response(
        200,
        json={
            "filename": "report.pdf",
            "title": "Annual Report",
            "markdown": "# Annual Report\n\nContent here.",
            "page_count": 5,
            "sections": ["Annual Report"],
            "char_count": 35,
            "byte_size": 10000,
        },
    ))
    result = await parse_document("report.pdf", b"%PDF-fake")
    assert result["title"] == "Annual Report"
    assert "markdown" in result
    assert result["page_count"] == 5


@pytest.mark.asyncio
@respx.mock
async def test_parse_document_service_error():
    respx.post(f"{DOCLING_URL}/parse").mock(return_value=httpx.Response(
        503, text="Service Unavailable"
    ))
    result = await parse_document("doc.pdf", b"data")
    assert "error" in result
    assert "503" in result["error"]


@pytest.mark.asyncio
async def test_parse_document_disabled():
    with patch("services.documents.DOCLING_ENABLED", False):
        result = await parse_document("doc.pdf", b"data")
    assert "error" in result
    assert "not enabled" in result["error"]


@pytest.mark.asyncio
@respx.mock
async def test_parse_document_connection_error():
    respx.post(f"{DOCLING_URL}/parse").mock(side_effect=httpx.ConnectError("refused"))
    result = await parse_document("doc.pdf", b"data")
    assert "error" in result


# ─── ingest_to_graph ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_to_graph_empty_markdown():
    result = await ingest_to_graph({"markdown": "", "title": "Empty"})
    assert "error" in result


@pytest.mark.asyncio
async def test_ingest_to_graph_calls_knowledge_import():
    """Each chunk triggers one knowledge_import call."""
    parsed = {
        "markdown": "Chunk A content.\n\nChunk B content.",
        "title": "Test Doc",
        "filename": "test.pdf",
    }
    import_calls = []

    async def mock_import(bundle, source_tag, trust_floor):
        import_calls.append(bundle)
        return {"imported": 1}

    with patch("services.documents.knowledge_import", mock_import):
        result = await ingest_to_graph(parsed)

    assert result["ingested_chunks"] >= 1
    assert result["title"] == "Test Doc"
    assert len(import_calls) == result["ingested_chunks"]
    # Each bundle must carry the document type
    for b in import_calls:
        assert b["@type"] == "DocumentChunk"
        assert b["source_filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_ingest_to_graph_handles_import_error():
    parsed = {"markdown": "Some content here.", "title": "Doc", "filename": "d.pdf"}

    async def fail_import(*a, **kw):
        raise RuntimeError("Neo4j down")

    with patch("services.documents.knowledge_import", fail_import):
        result = await ingest_to_graph(parsed)

    assert "error" in result
    assert "chunk 0" in result["error"]


# ─── visual_describe ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_visual_describe_success():
    respx.post(f"{SOVEREIGN_URL}/v1/chat/completions").mock(return_value=httpx.Response(
        200,
        json={"choices": [{"message": {"content": "This page shows a bar chart of quarterly revenue."}}]},
    ))
    result = await visual_describe(b"\x89PNG...", filename="page.png")
    assert "bar chart" in result
    assert not result.startswith("Error:")


@pytest.mark.asyncio
@respx.mock
async def test_visual_describe_sends_base64_image():
    """The image is sent as a base64-encoded data URI in the message content."""
    captured = {}

    def capture(request):
        import json
        body = json.loads(request.content)
        captured["messages"] = body["messages"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "A page."}}]})

    respx.post(f"{SOVEREIGN_URL}/v1/chat/completions").mock(side_effect=capture)
    img_bytes = b"\x89PNG\r\n\x1a\n"
    await visual_describe(img_bytes, filename="scan.png")

    content = captured["messages"][0]["content"]
    image_parts = [p for p in content if p.get("type") == "image_url"]
    assert len(image_parts) == 1
    url = image_parts[0]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == img_bytes


@pytest.mark.asyncio
@respx.mock
async def test_visual_describe_error_returns_error_string():
    respx.post(f"{SOVEREIGN_URL}/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("refused")
    )
    result = await visual_describe(b"data", filename="page.jpg")
    assert result.startswith("Error:")


# ─── health_check ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_health_check_ok():
    respx.get(f"{DOCLING_URL}/health").mock(return_value=httpx.Response(
        200, json={"status": "ok", "service": "moe-docling"}
    ))
    assert await health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_fail():
    respx.get(f"{DOCLING_URL}/health").mock(return_value=httpx.Response(503))
    assert await health_check() is False


@pytest.mark.asyncio
async def test_health_check_disabled():
    with patch("services.documents.DOCLING_ENABLED", False):
        assert await health_check() is True
