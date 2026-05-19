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

        setup_falco

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

setup_falco() {
    echo "▶ Setting up Falco (Tier 1 runtime security) …"

    # Falco runs as a systemd service on the host — NOT inside Docker.
    # Docker's seccomp filter blocks BPF_PROG_ATTACH on raw tracepoints even
    # with --privileged. The systemd service writes JSON events to
    # /var/log/falco/events.json which the codex-api container reads via
    # bind-mount. Requires: Proxmox cpu=host (or bare metal), Linux ≥ 5.8, BTF.

    # 1. perf_event_paranoid: Debian 12 defaults to 3 (blocks eBPF tracing).
    #    Falco modern_ebpf needs ≤ 2. Set persistently.
    local sysctl_file="/etc/sysctl.d/99-falco.conf"
    if ! grep -q "kernel.perf_event_paranoid" "$sysctl_file" 2>/dev/null; then
        echo "kernel.perf_event_paranoid = 2" | sudo tee "$sysctl_file" > /dev/null
        sudo sysctl -w kernel.perf_event_paranoid=2 >/dev/null
        echo "  ✓ perf_event_paranoid=2 set (persistent)"
    else
        echo "  ✓ perf_event_paranoid already configured"
    fi

    # 2. Install Falco if not present
    if ! command -v falco &>/dev/null; then
        echo "  Installing Falco package …"
        curl -fsSL https://falco.org/repo/falcosecurity-packages.asc \
            | sudo gpg --dearmor -o /usr/share/keyrings/falco-archive-keyring.gpg 2>/dev/null
        echo "deb [signed-by=/usr/share/keyrings/falco-archive-keyring.gpg] \
https://download.falco.org/packages/deb stable main" \
            | sudo tee /etc/apt/sources.list.d/falcosecurity.list > /dev/null
        sudo apt-get update -qq 2>/dev/null
        sudo apt-get install -y falco 2>&1 | grep -E "install|Setting up|already" || true
        echo "  ✓ Falco installed"
    else
        echo "  ✓ Falco already installed ($(falco --version 2>/dev/null | head -1 || echo 'unknown version'))"
    fi

    # 3. Configure Falco: JSON output → /var/log/falco/events.json
    sudo mkdir -p /var/log/falco
    if ! grep -q "^json_output: true" /etc/falco/falco.yaml 2>/dev/null; then
        sudo python3 -c "
import re, sys
content = open('/etc/falco/falco.yaml').read()
content = re.sub(r'^json_output: false', 'json_output: true', content, flags=re.MULTILINE)
content = content.replace(
    'file_output:\n  # -- Enable sending alerts to a file.\n  enabled: false\n  # -- If true, the file will be opened once and continuously written to.\n  # If false, the file will be reopened for each output message.\n  keep_alive: false\n  # -- Path to the file where alerts will be appended.\n  filename: ./events.txt',
    'file_output:\n  # -- Enable sending alerts to a file.\n  enabled: true\n  # -- If true, the file will be opened once and continuously written to.\n  # If false, the file will be reopened for each output message.\n  keep_alive: true\n  # -- Path to the file where alerts will be appended.\n  filename: /var/log/falco/events.json'
)
open('/etc/falco/falco.yaml', 'w').write(content)
"
        echo "  ✓ Falco configured: json_output → /var/log/falco/events.json"
    else
        echo "  ✓ Falco already configured"
    fi

    # 4. Enable and start the modern-bpf systemd service
    if ! systemctl is-active --quiet falco-modern-bpf.service 2>/dev/null; then
        sudo systemctl enable --now falco-modern-bpf.service 2>/dev/null || true
        sleep 3
    fi
    if systemctl is-active --quiet falco-modern-bpf.service 2>/dev/null; then
        echo "  ✓ falco-modern-bpf.service running (Tier 1 active)"
    else
        echo "  ⚠ Falco service did not start — check: journalctl -u falco-modern-bpf.service"
        echo "    Compliance will fall back to Tier 2 (Trivy). See docs/admin/compliance.md"
    fi
}

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
