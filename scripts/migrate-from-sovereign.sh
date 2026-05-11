#!/usr/bin/env bash
# moe-codex — clean-cut migration from a moe-sovereign installation that
# previously deployed Phase 16-24 (Marquez + lakeFS + NiFi + Drift events).
#
# Run this BEFORE you upgrade moe-sovereign past the phase-cleanup commit.
# It dumps the data-platform state, then restores it into a fresh moe-codex
# stack. After verification, the Phase 16-24 services in moe-sovereign can
# be removed (INSTALL_ENTERPRISE_DATA_STACK=false).
#
# Usage:
#   ./scripts/migrate-from-sovereign.sh             # full migration
#   ./scripts/migrate-from-sovereign.sh export-only # snapshot only, no restore
#   ./scripts/migrate-from-sovereign.sh restore-only # restore from existing snapshot

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_DIR="${MIGRATION_SNAPSHOT_DIR:-${ROOT}/migration-snapshot}"
STAMP="$(date +%Y%m%d-%H%M%S)"

cd "$ROOT"
[[ -f .env ]] || { echo "✗ .env missing"; exit 1; }
# shellcheck disable=SC1091
source .env

mode="${1:-all}"

# ── Helpers ─────────────────────────────────────────────────────────────────
say()  { printf "▶ %s\n" "$*"; }
ok()   { printf "  ✓ %s\n" "$*"; }
warn() { printf "  ! %s\n" "$*"; }

# ── Pre-flight ──────────────────────────────────────────────────────────────
say "Pre-flight: verifying source moe-sovereign stack reachable …"
docker exec moe-marquez   echo ok >/dev/null 2>&1 || { warn "moe-marquez not running in source stack"; }
docker exec moe-lakefs    echo ok >/dev/null 2>&1 || { warn "moe-lakefs not running in source stack"; }
docker exec moe-nifi      echo ok >/dev/null 2>&1 || { warn "moe-nifi not running in source stack"; }
docker exec terra_cache   echo ok >/dev/null 2>&1 || { warn "terra_cache (Valkey) not running"; }
ok "pre-flight complete"

mkdir -p "$SNAPSHOT_DIR"

# ── Export ──────────────────────────────────────────────────────────────────
if [[ "$mode" == "all" || "$mode" == "export-only" ]]; then
    say "Exporting Marquez postgres dump …"
    docker exec marquez-postgres pg_dump -U marquez marquez \
        > "${SNAPSHOT_DIR}/marquez-${STAMP}.sql"
    ok "$(du -h "${SNAPSHOT_DIR}/marquez-${STAMP}.sql" | cut -f1) → marquez-${STAMP}.sql"

    say "Exporting lakeFS postgres dump …"
    docker exec lakefs-postgres pg_dump -U lakefs lakefs \
        > "${SNAPSHOT_DIR}/lakefs-${STAMP}.sql"
    ok "$(du -h "${SNAPSHOT_DIR}/lakefs-${STAMP}.sql" | cut -f1) → lakefs-${STAMP}.sql"

    say "Exporting NiFi flow definition …"
    docker exec moe-nifi cat /opt/nifi/nifi-current/conf/flow.json.gz \
        > "${SNAPSHOT_DIR}/nifi-flow-${STAMP}.json.gz" 2>/dev/null \
        && ok "nifi-flow-${STAMP}.json.gz" \
        || warn "no flow.json.gz — NiFi may be using flow.xml.gz instead"
    docker exec moe-nifi cat /opt/nifi/nifi-current/conf/flow.xml.gz \
        > "${SNAPSHOT_DIR}/nifi-flow-${STAMP}.xml.gz" 2>/dev/null \
        && ok "nifi-flow-${STAMP}.xml.gz" || true

    say "Exporting Redis data-health drift events …"
    docker exec terra_cache valkey-cli --pass "${REDIS_PASSWORD:-}" \
        LRANGE moe:data_health:events 0 -1 \
        > "${SNAPSHOT_DIR}/drift-events-${STAMP}.jsonl" 2>/dev/null \
        && ok "$(wc -l < "${SNAPSHOT_DIR}/drift-events-${STAMP}.jsonl") drift events captured" \
        || warn "no drift events in Redis"

    say "MinIO knowledge bucket — leave in place (lakeFS still references it)"
    ok "  blobs remain in shared MinIO; lakeFS metadata pointer is in the postgres dump"

    [[ "$mode" == "export-only" ]] && { say "Export complete. Snapshot dir: $SNAPSHOT_DIR"; exit 0; }
fi

# ── Restore ─────────────────────────────────────────────────────────────────
if [[ "$mode" == "all" || "$mode" == "restore-only" ]]; then
    # Find newest snapshot if mode=restore-only
    if [[ "$mode" == "restore-only" ]]; then
        latest="$(ls -1t "${SNAPSHOT_DIR}"/marquez-*.sql 2>/dev/null | head -1 || true)"
        [[ -n "$latest" ]] || { echo "✗ no marquez-*.sql in $SNAPSHOT_DIR"; exit 1; }
        STAMP="$(basename "$latest" .sql | sed 's/^marquez-//')"
        say "Restoring snapshot $STAMP"
    fi

    say "Spinning up fresh codex stack …"
    docker compose up -d marquez-postgres lakefs-postgres
    sleep 8

    say "Restoring Marquez database …"
    docker exec -i marquez-postgres psql -U marquez -d marquez \
        < "${SNAPSHOT_DIR}/marquez-${STAMP}.sql"
    ok "marquez database restored"

    say "Restoring lakeFS database …"
    docker exec -i lakefs-postgres psql -U lakefs -d lakefs \
        < "${SNAPSHOT_DIR}/lakefs-${STAMP}.sql"
    ok "lakefs database restored"

    say "Starting codex-api + Marquez/lakeFS/NiFi …"
    docker compose up -d

    say "Restoring drift events into codex Redis index …"
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        docker exec terra_cache valkey-cli --pass "${REDIS_PASSWORD:-}" \
            -n 3 LPUSH moe:data_health:events "$line" >/dev/null
    done < "${SNAPSHOT_DIR}/drift-events-${STAMP}.jsonl" 2>/dev/null && ok "drift events restored"

    if [[ -f "${SNAPSHOT_DIR}/nifi-flow-${STAMP}.xml.gz" ]]; then
        say "Copying NiFi flow into fresh container …"
        docker cp "${SNAPSHOT_DIR}/nifi-flow-${STAMP}.xml.gz" \
            moe-nifi:/opt/nifi/nifi-current/conf/flow.xml.gz
        docker restart moe-nifi >/dev/null
        ok "NiFi flow restored (container restarted)"
    fi

    say "Verifying codex API …"
    sleep 5
    curl -fsS "http://localhost:${CODEX_HOST_PORT:-8090}/v1/codex/status" \
        | python3 -m json.tool \
        || warn "codex-api not responding yet — check logs"

    cat <<EOF

✓ Migration complete. Cutover steps for moe-sovereign:

    1. In moe-sovereign/.env:
         INSTALL_ENTERPRISE_DATA_STACK=false
         CODEX_URL=http://moe-codex-api:8090

    2. Bring down the now-orphaned Phase 16-24 services in moe-sovereign:
         cd /opt/deployment/moe-sovereign/moe-infra
         docker compose -f docker-compose.enterprise.yml down

    3. Upgrade moe-sovereign past the phase-cleanup commit.

    4. (Optional) Drop the moe-sovereign Phase-16-24 volumes:
         docker volume rm moe-infra_marquez_db_data moe-infra_lakefs_db_data

EOF
fi
