# Trino SQL Federation

MoE Codex bundles [Apache Trino](https://trino.io/) (Apache 2.0) as a distributed SQL
federation layer. It lets analysts query any connected data source with standard SQL —
no data movement required.

## Architecture

```
Client
  │
  ▼
POST /v1/codex/trino/query          ← codex-api (read-only gate)
  │
  ▼
moe-trino :8080                     ← Trino coordinator
  ├── postgresql  (terra_checkpoints)
  ├── memory      (session-scoped scratch space)
  └── tpch        (benchmark data — always available)
```

The `codex-api` acts as a read-only proxy: it blocks DDL (DROP / TRUNCATE / DELETE /
INSERT / UPDATE / ALTER) and enforces `max_rows`. All write operations must go through
the Trino CLI or a direct Trino connection.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `TRINO_URL` | `http://moe-trino:8080` | Trino coordinator URL |
| `TRINO_USER` | `codex` | Default query user |
| `TRINO_CATALOG` | `postgresql` | Default catalog |
| `TRINO_SCHEMA` | `public` | Default schema |
| `TRINO_ENABLED` | `true` | Disable Trino integration entirely |
| `TRINO_TIMEOUT` | `60` | HTTP timeout (seconds) |
| `TRINO_MAX_ROWS` | `1000` | Per-request row cap |
| `TRINO_HOST_PORT` | `8080` | Host port mapped to Trino container |
| `TRINO_PG_DB` | `postgres` | PostgreSQL database |
| `TRINO_PG_USER` | `postgres` | PostgreSQL user |
| `TRINO_PG_PASSWORD` | *(empty)* | PostgreSQL password |

## Catalogs

### `postgresql`

Federated access to `terra_checkpoints` — the shared Postgres instance from
moe-sovereign. Both the `public` (sovereign) and `codex` schemas are available.

```sql
-- all tables in the codex schema
SHOW TABLES FROM postgresql.codex;

-- cross-schema join
SELECT u.id, d.dataset_name
FROM   postgresql.public.users AS u
JOIN   postgresql.codex.datasets AS d ON d.owner_id = u.id
```

### `memory`

In-memory catalog for ad-hoc session-scoped computations.

```sql
CREATE TABLE memory.default.tmp AS SELECT * FROM postgresql.public.users LIMIT 100;
SELECT count(*) FROM memory.default.tmp;
```

### `tpch`

Standard TPC-H benchmark data for testing query plans and performance baselines.

```sql
SELECT count(*) FROM tpch.sf1.orders;
SELECT name, acctbal FROM tpch.sf1.customer LIMIT 10;
```

## API Endpoints

### `GET /v1/codex/trino/health`

Returns Trino reachability and configuration.

```json
{"trino_reachable": true, "trino_enabled": true, "trino_url": "http://moe-trino:8080"}
```

### `GET /v1/codex/trino/catalogs`

Lists all available catalogs.

### `GET /v1/codex/trino/schemas/{catalog}`

Lists schemas in a catalog.

### `GET /v1/codex/trino/tables/{catalog}/{schema}`

Lists tables in a schema.

### `POST /v1/codex/trino/query`

Execute a SQL query.

```json
{
  "sql": "SELECT count(*) FROM postgresql.public.users",
  "max_rows": 500
}
```

Response:

```json
{
  "columns": [{"name": "_col0", "type": "bigint"}],
  "rows":    [[4217]],
  "row_count": 1,
  "query_id": "20240101_120000_00001_xxxxx",
  "elapsed_ms": 143,
  "truncated": false
}
```

### `POST /v1/codex/trino/nl`

Translate a natural-language question to SQL via the `data_analyst` expert in
moe-sovereign, then execute it.

```json
{
  "question":    "How many datasets were imported last week?",
  "schema_hint": "CREATE TABLE codex.datasets (id INT, created_at TIMESTAMP, ...)",
  "max_rows":    100,
  "dry_run":     false
}
```

Set `dry_run: true` to get the generated SQL without executing it.

Response:

```json
{
  "question": "How many datasets were imported last week?",
  "sql":      "SELECT count(*) FROM postgresql.codex.datasets WHERE created_at >= NOW() - INTERVAL '7' DAY",
  "executed": true,
  "columns":  [{"name": "_col0", "type": "bigint"}],
  "rows":     [[12]],
  "row_count": 1,
  "elapsed_ms": 287,
  "truncated": false
}
```

## Security Notes

- The `/query` endpoint blocks all write SQL (DROP, TRUNCATE, DELETE, INSERT, UPDATE, ALTER).
  For DDL, use the Trino CLI: `trino --server http://moe-trino:8080 --catalog postgresql`.
- OPA markings are **not** enforced at the Trino level — Trino has direct Postgres access.
  Sensitive tables should be restricted at the Postgres role level (`GRANT SELECT ON ...`).
- The Trino container runs without TLS by default. For production, put it behind an
  internal reverse proxy with mTLS or restrict access to the internal Docker network only.

## Troubleshooting

**Trino returns `{"starting": true}`** — Trino is still initialising (can take 30-60s on
first start). Wait for the healthcheck to pass.

**`AUTHENTICATION_FAILED`** — The `TRINO_USER` does not have access to the requested
catalog. Check Trino access control configuration.

**`Table not found`** — Verify the fully-qualified name: `catalog.schema.table`.
Use `SHOW CATALOGS`, `SHOW SCHEMAS FROM <cat>`, `SHOW TABLES FROM <cat>.<schema>`.

**NL→SQL hallucination** — Provide a `schema_hint` with the relevant DDL to ground
the data_analyst expert. Use `dry_run: true` to inspect the generated SQL before
executing.
