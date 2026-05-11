# Migration: moe-sovereign Phase 16-24 → moe-codex

If you were running moe-sovereign with `INSTALL_ENTERPRISE_DATA_STACK=true`
(Phase 16-24: Marquez, lakeFS, NiFi, Catalog, Approval, Explorer, Drift,
Notebook), you migrate to moe-codex as a separate optional add-on with a
clean cut. This page walks you through it.

> **Why migrate?** Phase 16-24 served the Palantir-equivalent compliance
> use cases (catalog, lineage, versioning, audit trails). They are not
> the broad-market value of moe-sovereign and are now packaged in
> moe-codex so that compliance operators get a focused product and
> non-compliance operators get a leaner moe-sovereign.

---

## Pre-flight

1. **Both stacks ready:**
   - `moe-sovereign` is running with Phase 16-24 enabled.
   - `moe-codex` repo cloned next to it; `.env` configured.
2. **Snapshot dir mounted on a stable volume** (at least 5 GB free, more
   if you have heavy NiFi flow files):
   ```bash
   export MIGRATION_SNAPSHOT_DIR=/var/backups/moe-codex-migration
   sudo mkdir -p "$MIGRATION_SNAPSHOT_DIR"
   ```
3. **Plan a maintenance window** of 30-60 minutes. During the window the
   admin UI Catalog/Approval/Explorer pages are unavailable; ingest into
   moe-sovereign /v1/chat/completions stays online.

---

## Step 1 — Export from moe-sovereign

```bash
cd /opt/moe-codex
./scripts/migrate-from-sovereign.sh export-only
```

What gets exported:
- Marquez postgres dump → `marquez-<timestamp>.sql`
- lakeFS postgres dump → `lakefs-<timestamp>.sql`
- NiFi flow definition → `nifi-flow-<timestamp>.xml.gz`
- Redis data-health drift events → `drift-events-<timestamp>.jsonl`

MinIO blobs (the actual lakeFS-managed knowledge bundle data) **stay in
place** — codex reuses the shared MinIO. The lakeFS pointer is in the
postgres dump.

---

## Step 2 — Bring up codex

```bash
./install.sh up
```

`install.sh` waits for healthchecks, then runs MinIO bucket bootstrap and
lakeFS setup_lakefs. After ~90 s the stack is healthy.

---

## Step 3 — Restore into codex

```bash
./scripts/migrate-from-sovereign.sh restore-only
```

This imports the postgres dumps into the fresh codex `marquez-postgres`
and `lakefs-postgres`, then replays the drift events into the codex Redis
DB index (separate from moe-sovereign's `terra_cache` index 0/1/2).

Verify:
```bash
curl -s http://localhost:8090/v1/codex/status | jq
```

Expected:
```json
{
  "service": "moe-codex",
  "sovereign_reachable": true,
  "lineage_enabled":     true,
  "versioning_enabled":  true,
  "etl_enabled":         true,
  "redis_reachable":     true
}
```

---

## Step 4 — Cut moe-sovereign over

In `moe-sovereign/.env`, set:
```env
INSTALL_ENTERPRISE_DATA_STACK=false
CODEX_URL=http://moe-codex-api:8090
```

Then stop the now-orphaned Phase 16-24 services in moe-sovereign:
```bash
cd /opt/moe-sovereign/moe-infra
docker compose -f docker-compose.enterprise.yml down
```

Pull the moe-sovereign cleanup release (commit that removes Phase 16-24
code from the sovereign repo) and rebuild:
```bash
git pull
docker compose build moe-admin langgraph-app
docker compose up -d moe-admin langgraph-app
```

The sidebar entries `/catalog`, `/approval`, `/explorer`, `/notebook`,
`/enterprise` in the moe-sovereign admin UI now **redirect** to the
configured `CODEX_URL` when set, or **hide** when not set.

---

## Step 5 — (Optional) drop the now-orphaned volumes

After verifying that codex works for at least a week, the moe-sovereign
Phase-16-24 postgres volumes can be removed:

```bash
docker volume rm moe-infra_marquez_db_data moe-infra_lakefs_db_data
```

The MinIO bucket stays — codex still references its blobs through the
lakeFS pointer that we migrated in Step 3.

---

## Rollback

If migration goes wrong:

1. Stop codex: `cd /opt/moe-codex && docker compose down`
2. Restore moe-sovereign: `INSTALL_ENTERPRISE_DATA_STACK=true` back in `.env`
3. Bring the old enterprise stack back up: `docker compose -f docker-compose.enterprise.yml up -d`
4. The postgres volumes in moe-sovereign were **not modified** by the
   migration, so the old state is intact.

The snapshot files in `$MIGRATION_SNAPSHOT_DIR` are kept for 30 days as a
second safety net — delete them once codex is confirmed stable.
