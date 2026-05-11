# Document Intelligence

MoE Codex ships a Document Intelligence layer built on two open-source tools:

| Tool | License | Role |
|---|---|---|
| [DocLing](https://github.com/DS4SD/docling) (IBM) | MIT | Parse PDF/DOCX/PPTX/images → structured Markdown |
| ColPali-style visual description | — | Route page images to moe-sovereign vision expert |

## Architecture

```
Client
  │
  ├── POST /v1/codex/documents/parse     ─► moe-docling :7080/parse
  │                                                │
  │                                         DocLing converter
  │                                         (PDF/DOCX/PPTX → Markdown)
  │
  ├── POST /v1/codex/documents/ingest    ─► moe-docling :7080/parse
  │                                                │
  │                                    POST /graph/knowledge/import
  │                                         moe-sovereign GraphRAG
  │
  └── POST /v1/codex/documents/describe  ─► moe-sovereign vision_expert
                                              POST /v1/chat/completions
                                              (ColPali-style visual path)
```

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `DOCLING_URL` | `http://moe-docling:7080` | DocLing service URL |
| `DOCLING_ENABLED` | `true` | Disable document intelligence |
| `DOCLING_TIMEOUT` | `120` | HTTP timeout for parse requests (seconds) |
| `DOCLING_HOST_PORT` | `7080` | Host port mapped to moe-docling |
| `VISION_MODEL` | `vision_expert` | moe-sovereign model for visual description |
| `DOC_CHUNK_CHARS` | `4000` | Max characters per graph import chunk |

## Supported File Formats

| Format | Extension | Notes |
|---|---|---|
| PDF | `.pdf` | Text-based and scanned (with OCR) |
| Word | `.docx` | OOXML format |
| PowerPoint | `.pptx` | Slides → Markdown sections |
| Excel | `.xlsx` | Tables → Markdown tables |
| HTML | `.html`, `.htm` | Web pages |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` | OCR via Tesseract |

## API Endpoints

### `GET /v1/codex/documents/health`

```json
{"docling_reachable": true, "docling_enabled": true, "docling_url": "http://moe-docling:7080"}
```

### `POST /v1/codex/documents/parse`

Upload a document and receive its Markdown representation.

```bash
curl -X POST http://moe-codex:8090/v1/codex/documents/parse \
  -F "file=@report.pdf"
```

Response:

```json
{
  "filename":  "report.pdf",
  "title":     "Q3 Financial Report",
  "markdown":  "# Q3 Financial Report\n\n## Executive Summary\n\n...",
  "page_count": 12,
  "sections":  ["Q3 Financial Report", "Executive Summary", "Results"],
  "char_count": 18432,
  "byte_size":  204800
}
```

### `POST /v1/codex/documents/ingest`

Parse a document and ingest its text into the moe-sovereign knowledge graph.
The Markdown is chunked and imported via `/graph/knowledge/import` so GraphRAG
can retrieve it in future queries.

```bash
curl -X POST http://moe-codex:8090/v1/codex/documents/ingest \
  -F "file=@report.pdf" \
  -F "source_tag=finance-q3-2024" \
  -F "trust_floor=0.7"
```

Response:

```json
{
  "parse": {
    "filename": "report.pdf",
    "title": "Q3 Financial Report",
    "page_count": 12,
    "sections": ["Q3 Financial Report", "Executive Summary"],
    "char_count": 18432
  },
  "ingest": {
    "ingested_chunks": 5,
    "title": "Q3 Financial Report",
    "last_import": {"imported": 1}
  }
}
```

### `POST /v1/codex/documents/describe`

Upload a page image for visual understanding via the moe-sovereign vision expert.
This is the ColPali-style path for scan-heavy documents where text extraction
yields poor results.

```bash
curl -X POST http://moe-codex:8090/v1/codex/documents/describe \
  -F "file=@page_003.png" \
  -F "question=What figures and tables are shown on this page?"
```

Response:

```json
{
  "filename":    "page_003.png",
  "question":    "What figures and tables are shown on this page?",
  "description": "The page contains a bar chart comparing quarterly revenue..."
}
```

## Resource Sizing

The moe-docling container runs CPU-only PyTorch to avoid GPU conflicts with
inference nodes. Expected resource usage:

| Document type | Memory | Parse time |
|---|---|---|
| 10-page PDF (text) | ~500 MB | 2-5 s |
| 50-page PDF (mixed) | ~1.5 GB | 15-30 s |
| Image (OCR) | ~800 MB | 3-8 s |

The container is limited to 3 GB RAM and 2 CPUs. For larger document volumes,
increase `DOCLING_TIMEOUT` and the container memory limit accordingly.

## ColPali vs. DocLing — When to Use Which

| Scenario | Recommended path |
|---|---|
| Text-rich PDFs, DOCX, PPTX | `/parse` or `/ingest` — DocLing |
| Scanned PDFs with clean OCR | `/parse` — DocLing + Tesseract |
| Handwritten documents | `/describe` — vision expert |
| Complex infographics, diagrams | `/describe` — vision expert |
| Mixed (text + diagrams) | `/ingest` first, then `/describe` key pages |

## Troubleshooting

**`503 Service Unavailable`** — DocLing container is still starting (ML model load
takes 60-120 s on first boot). Check: `sudo docker logs moe-docling`.

**`415 Unsupported Media Type`** — Submit a supported file format. Password-protected
PDFs must be unlocked before uploading.

**Long parse times** — Set `DOCLING_TIMEOUT` to a higher value (e.g. 300 for large
scanned PDFs). The default 120 s is appropriate for typical office documents.

**Visual describe returns poor results** — Provide a more specific `question` field.
The vision expert performs better with targeted questions than generic descriptions.
