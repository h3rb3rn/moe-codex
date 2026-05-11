# MoE Codex

**EU-sovereign data and audit platform for [MoE Sovereign](https://github.com/h3rb3rn/moe-sovereign) — the open-source alternative to Palantir Foundry / Gotham / AIP.**

*Latin `codex` = manuscript collection, lawbook — thematic sibling of [moe-libris](https://github.com/h3rb3rn/moe-libris).*

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/Docs-docs.moe--sovereign.org-informational.svg)](https://docs.moe-sovereign.org/)
[![Comparison](https://img.shields.io/badge/Comparison-Palantir-orange.svg)](docs/system/palantir_comparison.md)

> **Repository topology.** `moe-codex` is an **optional** add-on to `moe-sovereign`. Operators who only need a sovereign multi-model LLM gateway run `moe-sovereign` alone. Operators who additionally need a data catalog, bundle versioning, lineage tracking, approval workflow, investigation Cypher explorer, and data-health drift detection (authorities, KritIS, pharma compliance, banking audit) deploy `moe-codex` alongside.

---

## What MoE Codex provides

| Module | Path | Palantir equivalent |
|---|---|---|
| **Data Catalog** | `/catalog` | Foundry Catalog |
| **Knowledge Approvals** | `/approval` | Foundry Branch Approval + Action Types |
| **Object Explorer** | `/explorer` | Gotham Object Drilldown |
| **Data Health & Drift** | `/health` | Foundry Health Checks |
| **JupyterLite Notebook** | `/notebook` | Foundry Code Workbook |
| **Lineage (Marquez)** | `/lineage` | Foundry Lineage |
| **Versioning (lakeFS)** | `/versioning` | Foundry Branching |
| **ETL Fan-Out (NiFi)** | `/etl` | Foundry Pipeline Builder |

Full feature-by-feature mapping: [`docs/system/palantir_comparison.md`](docs/system/palantir_comparison.md) (50 modules across Foundry/Gotham/AIP/Apollo, 12 industry use-cases).

---

## Quick Start

```bash
git clone https://github.com/h3rb3rn/moe-codex.git
cd moe-codex
cp .env.example .env
# Edit: CODEX_NODE_ID, CODEX_ADMIN_KEY, SOVEREIGN_URL (for GraphRAG attachment)

docker compose up -d

# Codex API:   http://localhost:8090
# Codex Docs:  http://localhost:8090/docs   (interactive OpenAPI)
# Marquez UI:  http://localhost:3010
# lakeFS UI:   http://localhost:8000
# NiFi UI:     http://localhost:8443/nifi/
```

Operators with an existing `moe-sovereign` installation that uses Phase 16-24 (formerly in moe-sovereign) should see [`docs/migration/from-sovereign.md`](docs/migration/from-sovereign.md) for a clean-cut migration including data transfer.

---

## Architecture

```
moe-sovereign  <- HTTP/REST ->  moe-codex  <-- Marquez (Lineage)
   (core)                       (codex)    <-- lakeFS (Versioning)
                                           <-- NiFi (ETL)
                                           <-- Postgres (shared terra_checkpoints)
                                           <-- Valkey (shared terra_cache)
```

**`moe-sovereign` runs autonomously without `moe-codex`.** Deploying codex adds the eight modules above. Communication uses clearly defined HTTP APIs (OpenAPI schemas in [`docs/api/`](docs/api/)).

---

## EU sovereignty & compliance

`moe-codex` is built for **authorities, KritIS, pharma compliance, banking audit** and similar compliance-driven operators:

- **GDPR Art. 32 + 35** (state of the art, DPIA) → [`docs/system/dsgvo_dpia_template.md`](docs/system/dsgvo_dpia_template.md)
- **EU AI Act (Regulation 2024/1689)** risk-class mapping → [`docs/system/eu_ai_act_mapping.md`](docs/system/eu_ai_act_mapping.md)
- **BSI-Grundschutz** baustein mapping → [`docs/system/bsi_grundschutz_mapping.md`](docs/system/bsi_grundschutz_mapping.md)
- **NIS2 readiness** → [`docs/system/nis2_readiness.md`](docs/system/nis2_readiness.md)

Hosting recommendation: Hetzner / IONOS / STACKIT / OVH / Scaleway — all under EU jurisdiction, no US CLOUD-Act exposure. Air-gap deployment documented.

---

## Status (2026-05-11)

| Phase | Component | Status |
|---|---|---|
| 16 | OpenLineage/Marquez | ✅ |
| 17 | NiFi ETL submission | ✅ |
| 18 | lakeFS bundle versioning | ✅ |
| 19 | Enterprise-stack dashboard | ✅ |
| 20 | Data Catalog | ✅ |
| 21 | Branch-based Approval | ✅ |
| 22 | Read-only Cypher Explorer | ✅ |
| 23 | Data Health drift detection | ✅ |
| 24 | JupyterLite Notebook | ✅ |

Planned extensions: OPA permissions, Trino SQL federation, DocLing document intelligence, Kestra pipeline builder, OpenSearch federated search, Cytoscape.js link analysis, vis-timeline, ArgoCD/Falco/OpenSCAP. Order driven by concrete use-case demand.

---

## License & license hygiene

Apache 2.0 (see [`LICENSE`](LICENSE)).

The stack uses **exclusively OSI-approved open-source components** and follows the Linux-Foundation-Fork principle — see [`docs/system/license_compliance.md`](docs/system/license_compliance.md) and the audit script [`scripts/audit-licenses.sh`](scripts/audit-licenses.sh). Concretely: OpenSearch instead of Elasticsearch, OpenTofu instead of Terraform, Apache Kafka instead of Confluent, Valkey instead of Redis ≥ 7.4, Meltano instead of Airbyte.

---

## Related repositories

- **[moe-sovereign](https://github.com/h3rb3rn/moe-sovereign)** — the MoE core (API gateway, 15 expert specialists, MCP precision tools, caching, GraphRAG basis)
- **[moe-libris](https://github.com/h3rb3rn/moe-libris)** — federation hub for knowledge bundle exchange between sovereign instances
- **[moe-codex](https://github.com/h3rb3rn/moe-codex)** — *this repository* — EU-Palantir alternative
