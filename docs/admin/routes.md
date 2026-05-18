# MoE Codex — Route Reference

This page lists every URL exposed by moe-codex and the moe-admin proxy,
organized by functional group. The admin UI routes are served by **moe-admin**
(moe-infra) at `https://admin.<your-domain>/`; the API routes are served by
**moe-codex** at `https://codex.<your-domain>/`.

---

## Navigation structure (Codex dropdown)

```
Codex ▾
├── Platform
│   ├── /codex          Overview & service status
│   ├── /catalog        Data catalog (Marquez + lakeFS + Neo4j)
│   ├── /approval       Branch-based approval workflow
│   └── /notebook       JupyterLab (full Python kernel)
│
├── BI & Analytics
│   ├── /superset       Apache Superset — dashboards, SQL pivot, charts
│   ├── /charts         Chart.js + PivotTable.js (Trino-backed)
│   ├── /timeseries     TimescaleDB time-series catalog + viewer
│   └── /search         OpenSearch federated full-text search
│
├── Investigation
│   ├── /dossier        Case file — pin evidence from all modules
│   ├── /explorer       Read-only Cypher explorer (Neo4j)
│   ├── /link-analysis  Cytoscape.js knowledge-graph visualization
│   ├── /timeline       vis-timeline unified event stream
│   └── /geo            Leaflet interactive map (PostGIS layers)
│
├── Pipelines & Content
│   ├── /kestra         Kestra pipeline builder (flows + executions)
│   ├── /forms          Schema-driven data-entry forms
│   ├── /workshop       Budibase low-code app builder
│   └── /notes          HedgeDoc collaborative Markdown notes
│
└── Security
    └── /compliance     Falco runtime alerts + OpenSCAP scan results
```

---

## Admin UI pages (moe-admin proxy)

All pages require login. They proxy to the moe-codex API via `CODEX_URL`.

### Platform

| Path | Function | Palantir equivalent |
|---|---|---|
| `/codex` | Codex hub — service status, version, reachability of all components | Foundry Overview |
| `/catalog` | Cross-source dataset browser (Marquez namespaces, lakeFS repos, Neo4j domains) | Foundry Catalog |
| `/approval` | List, approve, and reject pending knowledge bundles staged on lakeFS branches | Foundry Branch Approval |
| `/explorer` | Read-only Cypher editor against Neo4j; Neo4j Browser deep-link | Gotham Object Explorer |
| `/notebook` | JupyterLab server (proxy at `/notebook/lab`); 5 API snippets for orchestrator integration | Foundry Code Workbook |
| `/enterprise` | Legacy alias → redirects to `/codex` | — |

### BI & Analytics

| Path | Function | Palantir equivalent |
|---|---|---|
| `/superset` | Apache Superset dashboard picker + iframe embed via guest tokens; Trino auto-registration | Foundry Quiver / Workspace |
| `/charts` | Preset SQL queries rendered as Chart.js line/bar/pie + PivotTable.js; Superset deep-link | Foundry Quiver (partial) |
| `/timeseries` | TimescaleDB hypertable selector; window queries (1d/7d/30d/90d); Chart.js time-series | Foundry Time Series Catalog |
| `/search` | OpenSearch BM25+fuzzy full-text search across catalog, lakeFS, Kestra, lineage | Foundry Federated Search |

### Investigation

| Path | Function | Palantir equivalent |
|---|---|---|
| `/dossier` | Case file — create investigations, pin evidence from graph/timeline/geo/notes/compliance | Gotham Dossier |
| `/link-analysis` | Cytoscape.js graph of Neo4j entities and relationships; type + domain filter | Gotham Graph / Link Analysis |
| `/timeline` | vis-timeline.js: Marquez job runs + lakeFS commits + drift events in one view | Gotham Timeline |
| `/geo` | Leaflet interactive map; PostGIS layer picker; point-in-polygon lookup; CartoDB/OSM/Topo tiles | Foundry Geospatial / Gotham Geo |

### Pipelines & Content

| Path | Function | Palantir equivalent |
|---|---|---|
| `/kestra` | Kestra flow list, detail, trigger, execution monitor | Foundry Pipeline Builder (code-based) |
| `/forms` | Schema-driven data-entry forms generated from Kestra flow inputs; approval writeback | Foundry Forms |
| `/workshop` | Budibase app picker + iframe embed for published apps; direct builder link | Foundry Workshop |
| `/notes` | HedgeDoc real-time Markdown notes; create/list/view; session auth | Foundry Notepad / Reports |

### Security & Compliance

| Path | Function | Palantir equivalent |
|---|---|---|
| `/compliance` | Falco runtime alert table (priority filter, top-rules chart); OpenSCAP CIS scan results; on-demand scan trigger | Apollo Compliance Posture |

### Lineage & Versioning (Enterprise dashboard)

| Path | Function | Palantir equivalent |
|---|---|---|
| `/codex` → Enterprise tab | Marquez lineage run history, lakeFS versioning log, NiFi ETL status, data-health drift events | Foundry Lineage + Health Checks |
| `/pipeline-log` | LangGraph execution trace — per-request pipeline step log | AIP Studio execution log |
| `/token-timeline` | Token usage chart per user, per model, per day | AIP Usage Analytics |

---

## Codex REST API (moe-codex at `/v1/codex/`)

All endpoints require `Authorization: Bearer <SOVEREIGN_API_KEY>`.

### Status

| Method | Path | Function |
|---|---|---|
| GET | `/health` | Lightweight health probe (`{status: "ok"}`) |
| GET | `/v1/codex/status` | Full status — all services reachable flags |

### Catalog & Lineage

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/catalog/datasets` | Aggregate datasets from Marquez + Neo4j + lakeFS |
| GET | `/v1/codex/lineage/runs` | Recent Marquez job runs |
| GET | `/v1/codex/health/events` | Recent data-drift events (Redis) |

### Approval & Versioning

| Method | Path | Function |
|---|---|---|
| POST | `/v1/codex/approval/import/pending` | Stage bundle on lakeFS pending branch |
| POST | `/v1/codex/approval/approve` | Approve → import to Neo4j + merge lakeFS |
| POST | `/v1/codex/approval/reject` | Reject pending bundle |
| GET | `/v1/codex/approval/list` | List pending + recent approvals |
| GET | `/v1/codex/versioning/commits` | lakeFS commit log |

### Graph & Search

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/graph/network` | Cytoscape.js node/edge data from Neo4j |
| GET | `/v1/codex/graph/types` | Distinct entity types for filter dropdown |
| GET | `/v1/codex/search` | Federated search (OpenSearch → fallback keyword) |
| POST | `/v1/codex/search/index` | Re-index catalog into OpenSearch |
| GET | `/v1/codex/search/stats` | OpenSearch index stats |

### BI — Superset

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/superset/status` | Superset reachability probe |
| POST | `/v1/codex/superset/setup` | Register Trino connection (idempotent) |
| GET | `/v1/codex/superset/dashboards` | List published dashboards |
| GET | `/v1/codex/superset/token/{id}` | Issue guest token for iframe embed |

### BI — Trino SQL

| Method | Path | Function |
|---|---|---|
| POST | `/v1/codex/trino/query` | Execute read-only SQL; returns rows |
| GET | `/v1/codex/trino/tables` | List available tables |
| GET | `/v1/codex/trino/status` | Trino reachability probe |

### BI — Charts

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/charts/presets` | List built-in chart presets |
| POST | `/v1/codex/charts/query` | Run preset or custom chart query |

### Time Series

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/timeseries/status` | TimescaleDB reachability |
| GET | `/v1/codex/timeseries/tables` | List hypertables |
| GET | `/v1/codex/timeseries/query` | Query a metric table (window filter) |
| POST | `/v1/codex/timeseries/ingest` | Write an event record |

### Timeline

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/timeline` | Merged events: lineage + versioning + drift |

### Geospatial

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/geo/status` | PostGIS reachability |
| GET | `/v1/codex/geo/layers` | List geometry tables |
| GET | `/v1/codex/geo/layers/{table}/geojson` | GeoJSON FeatureCollection (bbox clip) |
| GET | `/v1/codex/geo/layers/{table}/config` | KeplerGL map config |
| GET | `/v1/codex/geo/pip` | Point-in-polygon lookup |

### Investigation — Dossier

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/dossier/list` | List all case files |
| POST | `/v1/codex/dossier/create` | Create a new case file |
| GET | `/v1/codex/dossier/{id}` | Get case file with pinned evidence |
| POST | `/v1/codex/dossier/{id}/pin` | Pin evidence item |
| DELETE | `/v1/codex/dossier/{id}/pin/{item}` | Unpin item |
| DELETE | `/v1/codex/dossier/{id}` | Delete case file |

### Pipelines

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/kestra/flows` | List Kestra flows |
| POST | `/v1/codex/kestra/trigger` | Trigger a flow execution |
| GET | `/v1/codex/kestra/executions` | List executions |
| POST | `/v1/codex/etl/submit` | Submit payload to NiFi ListenHTTP |
| GET | `/v1/codex/etl/status` | NiFi system diagnostics |
| GET | `/v1/codex/forms/schema/{ns}/{flow}` | JSON schema from Kestra flow inputs |

### Notes (HedgeDoc)

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/notes/status` | HedgeDoc reachability |
| GET | `/v1/codex/notes/list` | Recent notes |
| POST | `/v1/codex/notes/create` | Create note |
| GET | `/v1/codex/notes/{id}/embed` | Embed URL |

### Workshop (Budibase)

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/workshop/status` | Budibase reachability |
| GET | `/v1/codex/workshop/apps` | List published apps |
| GET | `/v1/codex/workshop/embed/{app_id}` | Embed URL |

### Document Intelligence

| Method | Path | Function |
|---|---|---|
| POST | `/v1/codex/documents/parse` | Upload file → Markdown + metadata (DocLing) |
| POST | `/v1/codex/documents/ingest` | Parse → ingest into knowledge graph |
| POST | `/v1/codex/documents/describe` | ColPali visual description of a page image |
| GET | `/v1/codex/documents/health` | DocLing reachability |

### AI & Safety

| Method | Path | Function |
|---|---|---|
| POST | `/v1/codex/opa/check` | OPA policy evaluation |
| POST | `/v1/codex/guardrails/check` | NeMo Guardrails prompt/response check |
| POST | `/v1/codex/guardrails/reload` | Reload guardrail config |
| GET | `/v1/codex/eval/runs` | MLflow experiment runs |
| POST | `/v1/codex/eval/log` | Log metrics to MLflow |

### Security — Compliance

| Method | Path | Function |
|---|---|---|
| GET | `/v1/codex/compliance/status` | Falco + SCAP availability |
| GET | `/v1/codex/compliance/falco/events` | Recent Falco runtime alerts |
| GET | `/v1/codex/compliance/falco/summary` | Alert counts by priority + top rules |
| GET | `/v1/codex/compliance/scap/summary` | Latest OpenSCAP scan results |
| POST | `/v1/codex/compliance/scan/trigger` | On-demand oscap scan |

---

## Port mapping (default)

| Service | Default port | Access |
|---|---|---|
| moe-admin (Admin UI) | 8088 | Reverse-proxied at `https://admin.<domain>/` |
| moe-codex API | 8090 | Internal; proxied through moe-admin |
| Marquez API | 5000 | Internal; proxied through moe-codex |
| Marquez Web UI | 3030 | Direct access for lineage graph debugging |
| lakeFS UI | 8010 | Direct access for bundle browsing |
| NiFi UI | 8443 | Direct access for flow editing |
| Kestra UI | 8082 | Direct access for pipeline editing |
| Apache Superset | 8088 | Embedded in `/superset`; also direct access |
| OpenSearch | 9200 | Internal; HTTP API only |
| OpenSearch Dashboards | 5601 | Direct access for index management |
| Budibase | 10000 | Embedded in `/workshop`; also direct access |
| HedgeDoc | 3002 | Embedded in `/notes`; also direct access |
| MLflow | 5001 | Direct access for experiment tracking |
| Grafana | 3001 | Monitoring dashboards |
| JupyterLab | 8899 | Proxied at `/notebook/`; direct for debugging |
