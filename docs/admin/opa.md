# OPA — Access Control & Data Markings

MoE Codex uses [Open Policy Agent](https://www.openpolicyagent.org/) (OPA) for fine-grained
access control on datasets and approval workflows. Policies are plain-text Rego files that can
be versioned, audited, and updated without redeploying the application.

## Architecture

```
Request → codex-api → OPA sidecar (/v1/data/<package>/<rule>)
                              ↑
                       policies/codex/*.rego  (mounted read-only)
```

OPA runs as a container (`moe-opa`) and exposes its REST API on port `8181` (mapped to host port
`8282` by default). The `codex-api` calls OPA for every catalog read and approval action.

## Policy Files

| File | Package | Controls |
|------|---------|---------|
| `policies/codex/data_markings.rego` | `codex.data_markings` | Clearance level vs. dataset classification |
| `policies/codex/catalog.rego` | `codex.catalog` | Dataset read / write / delete access |
| `policies/codex/approval.rego` | `codex.approval` | Submit / view / approve / reject bundles |

## Data Classification Levels

| Level | Value |
|-------|-------|
| `PUBLIC` | 0 (default) |
| `INTERNAL` | 1 |
| `RESTRICTED` | 2 |
| `CONFIDENTIAL` | 3 |
| `SECRET` | 4 |

A user's clearance must be **≥** the dataset's classification. A `RESTRICTED` dataset requires
`RESTRICTED`, `CONFIDENTIAL`, or `SECRET` clearance.

## Request Headers

Codex reads user context from HTTP headers set by moe-sovereign or the calling client:

| Header | Example | Meaning |
|--------|---------|---------|
| `X-Codex-User-Id` | `alice` | Authenticated user ID |
| `X-Codex-Groups` | `admin,approver` | Comma-separated group list |
| `X-Codex-Clearance` | `CONFIDENTIAL` | User clearance level |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPA_URL` | `http://moe-opa:8181` | OPA REST API endpoint |
| `OPA_ENABLED` | `true` | Set to `false` to bypass OPA (dev only) |
| `OPA_FAIL_OPEN` | `false` | If `true`, allow all requests when OPA is unreachable |
| `OPA_TIMEOUT` | `5` | Seconds before OPA call times out |

## Approval Workflow Groups

| Action | Required group |
|--------|---------------|
| `submit` | any authenticated user |
| `view` | any authenticated user |
| `approve` | `approver` or `admin` |
| `reject` | `approver` or `admin` |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/codex/opa/health` | OPA reachability check |
| `GET` | `/v1/codex/opa/config` | Current OPA configuration |
| `POST` | `/v1/codex/opa/evaluate` | Ad-hoc policy evaluation |
| `POST` | `/v1/codex/opa/check/catalog` | Catalog access check for calling user |
| `POST` | `/v1/codex/opa/check/approval` | Approval action check for calling user |

## Customising Policies

Edit the files in `policies/codex/`. Changes take effect immediately — OPA polls the mounted
directory every few seconds (no restart required).

Example: allow all users to read `PUBLIC` and `INTERNAL` datasets without clearance header:

```rego
# policies/codex/catalog.rego — custom read rule
allow {
    input.action == "read"
    classification_level[input.dataset.classification] <= 1  # PUBLIC or INTERNAL
}
```

## AI Act & BSI Compliance Note

OPA enforcement is required for:
- **High-risk AI Act** deployments (mandatory access control per Article 9)
- **BSI IT-Grundschutz ORP.4** (Identity and Access Management)
- **NIS2 healthcare/government** sectors (access restriction to sensitive data)
