# Backup & Restore Guide

MoE Codex has 11 stateful services. This page documents what needs to be
backed up, how to back it up, and how to restore each service.

---

## Stateful services

| Service | Container | Data location | Technology |
|---|---|---|---|
| Approval / Catalog DB | `moe-codex-api` (via Valkey) | `terra_cache` Redis DB | Redis AOF |
| Lineage metadata | `moe-marquez` | `marquez_db_data` volume | PostgreSQL dump |
| Data bundles | `moe-lakefs` | `lakefs_data` (Garage/MinIO) | S3-compatible |
| lakeFS metadata | `lakefs-postgres` | `lakefs_db_data` volume | PostgreSQL dump |
| ML experiments | `moe-mlflow` | `mlflow_artifacts` + `mlflow_db_data` | Artifacts + PostgreSQL |
| Pipeline state | `moe-kestra` | `kestra_db_data` | PostgreSQL dump |
| BI dashboards | `moe-superset` | `superset_db_data` | PostgreSQL dump |
| Search index | `moe-opensearch` | `opensearch_data` | OpenSearch snapshot |
| Collaborative notes | `moe-hedgedoc` | `hedgedoc_db_data` + `hedgedoc_uploads` | PostgreSQL + files |
| Geo data | `moe-postgis` | `postgis_data` | PostgreSQL dump (with PostGIS) |
| Time series | `moe-timescaledb` | `timescale_data` | PostgreSQL dump |
| Case files (Dossiers) | `terra_cache` | Redis key `codex:dossier:*` | Redis BGSAVE |

---

## Quick backup script

Save as `scripts/backup-codex.sh` and run from the moe-codex directory:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-/opt/backup/moe-codex/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$BACKUP_DIR"

echo "Backing up to $BACKUP_DIR"

# PostgreSQL dumps (all Postgres services)
for service in marquez lakefs mlflow kestra superset hedgedoc timescale postgis; do
  container="moe-${service}-db"
  # Some services use different container naming
  case "$service" in
    marquez)    container="marquez-postgres"; user="marquez"; db="marquez" ;;
    lakefs)     container="lakefs-postgres";  user="lakefs";  db="lakefs" ;;
    mlflow)     container="mlflow-postgres";  user="mlflow";  db="mlflow" ;;
    kestra)     container="moe-kestra-db";    user="kestra";  db="kestra" ;;
    superset)   container="moe-superset-db";  user="superset";db="superset" ;;
    hedgedoc)   container="moe-hedgedoc-db";  user="hedgedoc";db="hedgedoc" ;;
    timescale)  container="moe-timescaledb";  user="codex";   db="timeseries" ;;
    postgis)    container="moe-postgis";      user="codex_geo";db="geodata" ;;
  esac
  echo "  Dumping $db from $container…"
  sudo docker exec "$container" \
    pg_dump -U "$user" -Fc "$db" \
    > "$BACKUP_DIR/${service}.dump" 2>/dev/null || \
    echo "    WARNING: $container not running, skipping"
done

# OpenSearch snapshot (via API)
OS_URL="${OPENSEARCH_URL:-http://localhost:9200}"
curl -sf -X PUT "$OS_URL/_snapshot/backup_repo" \
  -H 'Content-Type: application/json' \
  -d '{"type":"fs","settings":{"location":"/usr/share/opensearch/snapshots"}}' \
  > /dev/null 2>&1 || true
curl -sf -X PUT "$OS_URL/_snapshot/backup_repo/snap_$(date +%Y%m%d)" \
  > /dev/null 2>&1 && echo "  OpenSearch snapshot created" || \
  echo "  WARNING: OpenSearch not reachable, skipping"

# Redis BGSAVE (dossiers + approval state)
echo "  Redis BGSAVE…"
sudo docker exec terra_cache redis-cli BGSAVE > /dev/null 2>&1 || true
sleep 2
sudo docker cp terra_cache:/data/dump.rdb "$BACKUP_DIR/redis.rdb" 2>/dev/null || \
  echo "  WARNING: Redis not reachable, skipping"

# lakeFS objects (stored in Garage/MinIO — back up the volume)
echo "  Backing up lakeFS object store volume…"
sudo docker run --rm \
  -v lakeFS_data:/data:ro \
  -v "$BACKUP_DIR":/out \
  alpine tar -czf /out/lakefs_objects.tar.gz -C /data . 2>/dev/null || \
  echo "  WARNING: lakeFS volume not found, skipping"

echo ""
echo "Backup complete: $BACKUP_DIR"
du -sh "$BACKUP_DIR"
```

---

## Service-by-service restore

### PostgreSQL services

```bash
# Generic restore — substitute container/user/db as needed
sudo docker exec -i <container> \
  pg_restore -U <user> -d <db> --clean --if-exists < backup.dump
```

Example for Superset:

```bash
sudo docker exec -i moe-superset-db \
  pg_restore -U superset -d superset --clean --if-exists < superset.dump
sudo docker compose restart moe-superset
```

### OpenSearch

```bash
# List available snapshots
curl -s http://localhost:9200/_snapshot/backup_repo/_all | jq '.snapshots[].snapshot'

# Restore a snapshot
curl -X POST http://localhost:9200/_snapshot/backup_repo/snap_20260101/_restore \
  -H 'Content-Type: application/json' \
  -d '{"indices": "codex_unified", "ignore_unavailable": true}'
```

### Redis (dossiers + approval state)

```bash
# Stop Redis, copy the dump, restart
sudo docker stop terra_cache
sudo docker cp redis.rdb terra_cache:/data/dump.rdb
sudo docker start terra_cache
```

### lakeFS objects

```bash
# Restore the Garage/MinIO object store volume
sudo docker run --rm \
  -v lakeFS_data:/data \
  -v /path/to/backup:/in:ro \
  alpine tar -xzf /in/lakefs_objects.tar.gz -C /data
```

---

## Backup schedule recommendation

| Frequency | Services |
|---|---|
| **Daily** | All PostgreSQL services (marquez, lakefs, mlflow, kestra, superset, hedgedoc, timescale, postgis) |
| **Daily** | Redis BGSAVE (dossiers, approval state) |
| **Weekly** | lakeFS object store (Garage volume) |
| **On change** | OpenSearch snapshot (after catalog re-index) |

A simple cron entry (add to `/etc/cron.d/moe-codex-backup`):

```
0 2 * * * root bash /opt/moe-codex/scripts/backup-codex.sh >> /var/log/moe-codex-backup.log 2>&1
```

---

## Disaster recovery priority

If you must choose what to restore first:

1. **lakeFS** — contains all knowledge bundles (the primary data asset)
2. **Marquez** — lineage metadata (reconstructable from re-running pipelines, but takes time)
3. **Superset** — dashboards (user-created; hard to recreate manually)
4. **HedgeDoc** — investigation notes
5. **TimescaleDB / PostGIS** — operational data; easiest to re-ingest from source
6. **Kestra** — flow definitions are in git; execution history less critical
7. **MLflow** — experiment metadata; models usually stored separately
8. **Redis** — dossiers are relatively lightweight and low-criticality

> **Note:** Neo4j (the moe-sovereign knowledge graph) is backed up separately
> via moe-sovereign's backup procedure — see `moe-infra/docs/admin/backup.md`.
