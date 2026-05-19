# Compliance Posture — Admin Guide

MoE Codex implements a two-tier runtime security architecture that works on both
bare-metal servers and QEMU/KVM virtual machines.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Tier 1 — Falco (preferred, requires cpu=host or HW)    │
│  systemd service → /var/log/falco/events.json           │
│  ↓ bind-mounted read-only into codex-api container      │
└─────────────────────────────────────────────────────────┘
         fallback if Falco unavailable
┌─────────────────────────────────────────────────────────┐
│  Tier 2 — Trivy (works everywhere, on-demand)           │
│  Docker socket → container image CVE scan               │
└─────────────────────────────────────────────────────────┘
```

The active tier is shown in the Compliance UI badge and in `/v1/codex/compliance/status`.

## Tier 1: Falco (Runtime Syscall Monitoring)

### Why systemd, not Docker

Falco's `modern_ebpf` probe attaches BPF programs to raw syscall tracepoints
(`raw_tracepoints/sys_enter`, `raw_tracepoints/sys_exit`). Docker's internal
seccomp filter blocks `bpf(BPF_PROG_ATTACH)` on these tracepoints even with
`--privileged`. Running Falco as a host systemd service bypasses this and gives
the probe direct kernel access.

### Host Requirements

| Requirement | Check | Notes |
|---|---|---|
| Linux kernel ≥ 5.8 | `uname -r` | BTF + ringbuf support |
| BTF available | `ls /sys/kernel/btf/vmlinux` | Required for CO-RE |
| `perf_event_paranoid` ≤ 2 | `cat /proc/sys/kernel/perf_event_paranoid` | Debian 12 defaults to 3 — installer sets 2 |
| CPU model exposes hardware features | `cpu=host` in Proxmox | QEMU default `cpu=qemu` blocks `BPF_MAP_TYPE_RINGBUF` |

### Proxmox / QEMU KVM Setup

In Proxmox PVE, set the VM CPU type to **host** before starting the stack:

1. Proxmox UI → VM → Hardware → Processors → Type: **host**
2. Restart the VM
3. Run `./install.sh up` — Falco will be installed and started automatically

### Managing the service

```bash
# Status
sudo systemctl status falco-modern-bpf.service

# View live events
sudo journalctl -u falco-modern-bpf.service -f

# Restart after config change
sudo systemctl restart falco-modern-bpf.service

# View JSON events (also read by codex-api)
sudo tail -f /var/log/falco/events.json | python3 -m json.tool
```

### Configuration

Falco configuration lives at `/etc/falco/falco.yaml`. Key settings managed by
the installer:

```yaml
json_output: true          # Required for codex-api to parse events
file_output:
  enabled: true
  keep_alive: true
  filename: /var/log/falco/events.json
```

Custom rules can be added to `/etc/falco/rules.d/`.

### Known Alerts

The PostGIS health-check script (`pg_isready`) reads `/etc/shadow` via Perl —
this triggers a Falco **Warning** (`Read sensitive file trusted after startup`).
This is a known false positive. To suppress it, add to `/etc/falco/rules.d/local.yaml`:

```yaml
- rule: Read sensitive file trusted after startup
  condition: >
    sensitive_files and evt.type = openat
    and not proc.name in (pg_isready, postgres, pg_ctlcluster)
  override:
    condition: append
```

## Tier 2: Trivy (Container Image CVE Scanning)

Trivy is always available as a fallback and can be triggered independently.
It requires the Docker socket to be mounted into the codex-api container
(`/var/run/docker.sock:ro`), which is the default configuration.

### Triggering a scan

Via the Compliance UI: click **Trivy Scan** button.

Via the API:
```bash
curl -X POST http://localhost:8090/v1/codex/compliance/trivy/trigger
```

Results are cached as JSON in `/var/lib/codex/trivy/` (Docker volume).

## API Reference

| Endpoint | Description |
|---|---|
| `GET /v1/codex/compliance/status` | Active tier, reachability |
| `GET /v1/codex/compliance/falco/events?limit=100` | Recent Falco alerts |
| `GET /v1/codex/compliance/falco/summary` | Alert counts by priority |
| `POST /v1/codex/compliance/scan/trigger` | Trigger scan (auto-selects tier) |
| `GET /v1/codex/compliance/trivy/summary` | Latest Trivy CVE counts |
| `POST /v1/codex/compliance/trivy/trigger` | Trigger Trivy image scan |
