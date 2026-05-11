# MoE Codex

**EU-Souveräne Daten- und Audit-Plattform für [MoE Sovereign](https://github.com/h3rb3rn/moe-sovereign) — die Open-Source-Alternative zu Palantir Foundry / Gotham / AIP.**

*Lateinisch `codex` = Manuskript-Sammlung, Gesetzbuch — passt thematisch zur Geschwister-Plattform [moe-libris](https://github.com/h3rb3rn/moe-libris).*

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/Docs-docs.moe--sovereign.org-informational.svg)](https://docs.moe-sovereign.org/)
[![Comparison](https://img.shields.io/badge/Vergleich-Palantir-orange.svg)](docs/system/palantir_comparison.md)

> **Repository-Topologie:** `moe-codex` ist ein **optionales** Add-on zu `moe-sovereign`. Wer nur einen souveränen Multi-Model-LLM-Gateway braucht, kommt mit `moe-sovereign` aus. Wer zusätzlich Daten-Katalog, Bundle-Versionierung, Lineage, Approval-Workflow, Investigation-Cypher-Explorer und Data-Health-Drift-Detection benötigt (Behörden, KritIS, Pharma-Compliance, Banken-Audit), deployt zusätzlich `moe-codex`.

---

## Was MoE Codex liefert

| Modul | Pfad | Palantir-Pendant |
|---|---|---|
| **Data Catalog** | `/catalog` | Foundry Catalog |
| **Knowledge Approvals** | `/approval` | Foundry Branch-Approval + Action Types |
| **Object Explorer** | `/explorer` | Gotham Object Drilldown |
| **Data Health & Drift** | `/health` | Foundry Health Checks |
| **JupyterLite Notebook** | `/notebook` | Foundry Code Workbook |
| **Lineage (Marquez)** | `/lineage` | Foundry Lineage |
| **Versioning (lakeFS)** | `/versioning` | Foundry Branching |
| **ETL Fan-Out (NiFi)** | `/etl` | Foundry Pipeline Builder |

Vollständige Gegenüberstellung: [`docs/system/palantir_comparison.md`](docs/system/palantir_comparison.md) (50 Module über Foundry/Gotham/AIP/Apollo, 12 Branchen-Use-Cases).

---

## Quick Start

```bash
git clone https://github.com/h3rb3rn/moe-codex.git
cd moe-codex
cp .env.example .env
# Edit: CODEX_NODE_ID, CODEX_ADMIN_KEY, SOVEREIGN_URL (für GraphRAG-Anbindung)

docker compose up -d

# Codex-API:    http://localhost:8090
# Codex-Docs:   http://localhost:8090/docs   (OpenAPI)
# Marquez UI:   http://localhost:3010
# lakeFS UI:    http://localhost:8000
# NiFi UI:      http://localhost:8443/nifi/
```

Wer bereits eine `moe-sovereign`-Installation hat und Phase 16-24 (ehemals in moe-sovereign) bereits nutzt: siehe [`docs/migration/from-sovereign.md`](docs/migration/from-sovereign.md) für sauberen Übergang inklusive Daten-Migration.

---

## Architektur

```
moe-sovereign  ◄─ HTTP/REST ─►  moe-codex  ◄── Marquez (Lineage)
   (Kern)                       (Codex)    ◄── lakeFS (Versioning)
                                           ◄── NiFi (ETL)
                                           ◄── Postgres (shared terra_checkpoints)
                                           ◄── Valkey (shared terra_cache)
```

**`moe-sovereign` kann ohne `moe-codex` laufen.** Wer Codex deployt, bekommt zusätzlich die acht Module oben. Die Kommunikation läuft über klar definierte HTTP-APIs (OpenAPI-Schemas in [`docs/api/`](docs/api/)).

---

## EU-Souveränität & Compliance

`moe-codex` ist explizit für **Behörden, KritIS, Pharma-Compliance, Banken-Audit** und ähnliche compliance-getriebene Operatoren gebaut:

- **DSGVO Art. 32 + 35** (Stand der Technik, DPIA) → [`docs/system/dsgvo_dpia_template.md`](docs/system/dsgvo_dpia_template.md)
- **EU AI Act (Verordnung 2024/1689)** Risikoklassen-Mapping → [`docs/system/eu_ai_act_mapping.md`](docs/system/eu_ai_act_mapping.md)
- **BSI-Grundschutz** Bausteine-Mapping → [`docs/system/bsi_grundschutz_mapping.md`](docs/system/bsi_grundschutz_mapping.md)
- **NIS2 Readiness** → [`docs/system/nis2_readiness.md`](docs/system/nis2_readiness.md)

Hosting-Empfehlung: Hetzner / IONOS / STACKIT / OVH / Scaleway — alles unter EU-Rechtsraum, kein US-CLOUD-Act-Bezug. Air-Gap-Deployment dokumentiert.

---

## Status (2026-05-11)

| Phase | Komponente | Status |
|---|---|---|
| 16 | OpenLineage/Marquez | ✅ |
| 17 | NiFi ETL Submission | ✅ |
| 18 | lakeFS Bundle Versioning | ✅ |
| 19 | Enterprise-Stack-Dashboard | ✅ |
| 20 | Data Catalog | ✅ |
| 21 | Branch-based Approval | ✅ |
| 22 | Read-only Cypher Explorer | ✅ |
| 23 | Data Health Drift Detection | ✅ |
| 24 | JupyterLite Notebook | ✅ |

Geplante Erweiterungen (Tracks D.1–D.3 im Sovereign-Plan, jetzt hier umgesetzt): OPA Permissions, Trino SQL Federation, DocLing Document Intelligence, Kestra Pipeline Builder, OpenSearch Federated Search, Cytoscape.js Link Analysis, vis-timeline, ArgoCD/Falco/OpenSCAP. Reihenfolge nach Use-Case-Bedarf.

---

## Lizenz & Lizenz-Hygiene

Apache 2.0 (siehe [`LICENSE`](LICENSE)).

Wir verwenden **ausschließlich OSI-konforme Open-Source-Komponenten** und folgen dem Linux-Foundation-Fork-Prinzip — siehe [`docs/system/license_compliance.md`](docs/system/license_compliance.md) und das Audit-Skript [`scripts/audit-licenses.sh`](scripts/audit-licenses.sh). Konkret: OpenSearch statt Elasticsearch, OpenTofu statt Terraform, Apache Kafka statt Confluent, Valkey statt Redis ≥ 7.4, Meltano statt Airbyte.

---

## Verwandte Repos

- **[moe-sovereign](https://github.com/h3rb3rn/moe-sovereign)** — der MoE-Kern (API-Gateway, 15 Experten, MCP, Caching, GraphRAG-Basis)
- **[moe-libris](https://github.com/h3rb3rn/moe-libris)** — Federation Hub für Wissens-Bündel-Austausch zwischen Sovereign-Instanzen
- **[moe-codex](https://github.com/h3rb3rn/moe-codex)** — *dieses Repo* — EU-Palantir-Alternative
