# Data Onboarding

This page covers moving data from its source into MoE Codex in a way that is versioned, lineage-tracked, and ready for catalog annotation.

## Knowledge Bundle Format

The primary ingest unit is a **knowledge bundle** — a JSON-LD file that defines entities and their relationships for the Neo4j GraphRAG graph in moe-sovereign.

```json
{
  "@context": "https://schema.org/",
  "@graph": [
    {
      "@id": "entity:DATASET-001",
      "@type": "Dataset",
      "name": "Cohort Phenotype v2.3",
      "description": "...",
      "dateModified": "2024-11-15",
      "creator": { "@type": "Organization", "name": "Research Consortium XY" }
    }
  ]
}
```

Use `POST /v1/graph/knowledge/import` on the moe-sovereign API to ingest. This endpoint is the legitimate import path without requiring an Approval Gate — use it for trusted, already-reviewed datasets.

## lakeFS Branch Strategy

| Branch pattern | Purpose | Who writes | Who approves |
|----------------|---------|-----------|-------------|
| `raw/<source>/<yyyymmdd-hhmmss>` | Immutable ingest snapshot | NiFi / ETL pipeline | Nobody — never modified |
| `pending/<tag>-<timestamp>` | Awaiting approval | Analyst / pipeline | Approver via `/approval` UI |
| `approved/<project>/<version>` | Approved for use | Approval gate merge | Approver's lakeFS merge |
| `publish/<version>` | Ready for external export | Analyst | DPO or data owner |

**Never** write directly to `approved/` or `publish/`. Use the approval gate merge.

## NiFi Pipeline Patterns

### Pattern 1: Batch ingest from file system

```
GetFile → ValidateRecord → ConvertRecord (→ Parquet)
→ PutS3Object (lakeFS: raw/<source>/<ts>/)
→ PublishKafka (topic: codex.ingest.complete)
```

### Pattern 2: Streaming ingest via HTTP

```
ListenHTTP (port 9999) → EvaluateJsonPath → RouteOnAttribute
→ PutS3Object (lakeFS: raw/<source>/<ts>/)
→ PublishKafka (topic: codex.ingest.complete)
```

### Pattern 3: Lineage event emission

After every significant transform, emit an OpenLineage event:

```
InvokeHTTP (POST https://marquez:8080/api/v1/lineage)
Content-Type: application/json
Body: { "eventType": "COMPLETE", "run": {...}, "job": {...}, "inputs": [...], "outputs": [...] }
```

## Approval Gate Flow

1. Analyst submits dataset: `POST /v1/versioning/commit` → creates lakeFS `pending/<tag>-<ts>` branch.
2. Admin sees pending item in `/approval` UI.
3. Admin reviews, adds comments, accepts or rejects.
4. On accept: lakeFS merge to `approved/`, Marquez lineage event `APPROVAL_GRANTED` emitted.
5. On reject: Marquez lineage event `APPROVAL_REJECTED` + notification to submitter.

## Catalog Annotation

After a dataset lands in `approved/`, catalog it via the `/catalog` UI or API:

```bash
curl -X POST http://moe-codex:8200/v1/catalog/entry \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cohort Phenotype v2.3",
    "source": "lakeFS:approved/cohort-phenotype/v2.3",
    "description": "...",
    "tags": ["clinical", "approved", "fair"],
    "gdpr_category": "personal_data"
  }'
```

A catalog entry makes the dataset discoverable via natural language queries through moe-sovereign GraphRAG.
