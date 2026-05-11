#!/usr/bin/env bash
# moe-codex installer.
#
# Usage:
#   ./install.sh              # bootstrap + start
#   ./install.sh status       # show health of all services
#   ./install.sh logs <svc>   # tail logs of a service
#   ./install.sh down         # stop the stack (keeps volumes)
#
# Requires moe-sovereign to be running (joins its network for shared state).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

[[ -f .env ]] || { echo "✗ .env missing — copy from .env.example first"; exit 1; }

# shellcheck disable=SC1091
source .env

cmd="${1:-up}"

case "$cmd" in
    up)
        echo "▶ Pre-flight: verifying moe-sovereign network is reachable …"
        docker network inspect moe-infra_default >/dev/null 2>&1 \
            || { echo "✗ moe-sovereign network 'moe-infra_default' not found. Start moe-sovereign first."; exit 2; }

        echo "▶ Pulling images …"
        docker compose pull 2>&1 | grep -E "Pulled|Pull complete|Status" | tail -10 || true

        echo "▶ Building codex-api image …"
        docker compose build codex-api

        echo "▶ Starting stack …"
        docker compose up -d

        echo "▶ Waiting for health checks (90s max) …"
        for i in $(seq 1 18); do
            healthy=$(docker compose ps --format json 2>/dev/null \
                | python3 -c "import sys,json; lines=[l for l in sys.stdin.read().splitlines() if l]; ok=sum(1 for l in lines if json.loads(l).get('Health') in ('healthy','')) ; print(ok)")
            if [[ "$healthy" -ge 5 ]]; then
                echo "  ✓ Services healthy ($i*5s)"
                break
            fi
            sleep 5
        done

        bootstrap_lakefs
        bootstrap_minio_bucket

        echo
        echo "▶ Service URLs:"
        echo "  Codex API   : http://localhost:${CODEX_HOST_PORT:-8090}"
        echo "  Codex Docs  : http://localhost:${CODEX_HOST_PORT:-8090}/docs"
        echo "  Marquez UI  : http://localhost:${MARQUEZ_WEB_PORT:-3030}"
        echo "  lakeFS UI   : http://localhost:${LAKEFS_HOST_PORT:-8010}"
        echo "  NiFi UI     : http://localhost:${NIFI_HOST_PORT:-8181}/nifi/"
        ;;

    down)
        docker compose down
        ;;

    status)
        docker compose ps
        echo
        curl -s "http://localhost:${CODEX_HOST_PORT:-8090}/v1/codex/status" | python3 -m json.tool || true
        ;;

    logs)
        docker compose logs -f --tail 100 "${2:-codex-api}"
        ;;

    *)
        echo "Unknown command: $cmd"
        echo "Usage: $0 {up|down|status|logs <service>}"
        exit 1
        ;;
esac

# ─── Helpers ────────────────────────────────────────────────────────────────

bootstrap_minio_bucket() {
    echo "▶ Bootstrapping MinIO bucket 'knowledge' …"
    # MinIO bucket creation via aws CLI in the moe-storage container.
    docker exec moe-storage mc alias set codex http://localhost:9000 \
        "${MINIO_ROOT_USER:-moeadmin}" "${MINIO_ROOT_PASSWORD}" >/dev/null 2>&1 || true
    docker exec moe-storage mc mb codex/knowledge --ignore-existing >/dev/null 2>&1 \
        && echo "  ✓ bucket ready" || echo "  (mc not in MinIO image — bucket auto-created on first lakeFS write)"
}

bootstrap_lakefs() {
    echo "▶ Bootstrapping lakeFS installation (idempotent) …"
    # The v1.81 image needs an explicit setup_lakefs call; LAKEFS_INSTALLATION_* envs
    # do not auto-trigger setup. See enterprise_stack_quirks.
    docker exec moe-lakefs wget -qO- \
        --post-data="{\"username\":\"${CODEX_ADMIN_USER:-admin}\",\"key\":{\"access_key_id\":\"${LAKEFS_ACCESS_KEY_ID}\",\"secret_access_key\":\"${LAKEFS_SECRET_ACCESS_KEY}\"}}" \
        --header="Content-Type: application/json" \
        http://localhost:8000/api/v1/setup_lakefs >/dev/null 2>&1 \
        && echo "  ✓ lakeFS installation initialised" \
        || echo "  (lakeFS already initialised — OK)"
}
