# BSI-Grundschutz — Baustein Mapping

Skeleton mapping of MoE Codex components onto BSI IT-Grundschutz
*Bausteine* (Edition 2023). Operators undergoing C5 / ISO 27001 / KritIS
audits use this as a starting point.

> **Status:** skeleton (2026-05). Baustein contents are not yet fully
> commented; `TODO:` markers identify gaps that must be closed in the
> concrete operator context.

The Baustein identifiers (e.g. `OPS.1.1.5`) are kept in their original
German codes because they are the official BSI identifiers used in audit
documentation.

---

## ISMS layer

| Baustein | Relevance for codex | Satisfied by |
|---|---|---|
| ISMS.1 Security management | Operator obligation | TODO |

## ORP layer (Organisation / Personnel)

| Baustein | Relevance | Satisfied by |
|---|---|---|
| ORP.4 Identity and access management | High | Authentik OIDC + RBAC; OPA markings layer (planned) |

## CON layer (Conception)

| Baustein | Relevance | Satisfied by |
|---|---|---|
| CON.1 Crypto concept | High | TLS via Caddy; Authentik sessions; lakeFS secret key |
| CON.3 Backup concept | High | `migrate-from-sovereign.sh` shows backup path; postgres-dump pattern |

## OPS layer (Operations)

| Baustein | Relevance | Satisfied by |
|---|---|---|
| OPS.1.1.2 Proper IT administration | High | install.sh + migration script + audit script |
| OPS.1.1.4 Protection against malware | Medium | TODO — operator obligation (Falco optional in later phase) |
| OPS.1.1.5 Logging | High | Marquez run events, drift events, Kafka `moe.audit` |
| OPS.1.1.6 Software testing and releases | High | pytest 287+/287 green as release gate |

## APP layer (Applications)

| Baustein | Relevance | Satisfied by |
|---|---|---|
| APP.3.3 Web applications | High | FastAPI with Pydantic validation; Caddy as reverse proxy |
| APP.4.3 Relational database systems | High | Postgres with Authentik auth; backup via pg_dump |
| APP.5.3 Big data | Medium | Marquez / lakeFS are big-data-adjacent — TODO precise placement |

## SYS layer (Systems)

| Baustein | Relevance | Satisfied by |
|---|---|---|
| SYS.1.1 General server | High | Container hardening (read-only fs, no-new-privs) |
| SYS.1.6 Containerisation | High | Docker Compose with explicit `cap_drop`, network isolation |

## NET layer (Network)

| Baustein | Relevance | Satisfied by |
|---|---|---|
| NET.3.2 Firewall | High | Operator obligation (e.g. Hetzner / IONOS firewall) |
| NET.3.3 VPN | Medium | TODO — operator-specific |

## INF layer (Infrastructure)

Entirely operator-specific. Hosting recommendations: see
[`eu_sovereignty_charter.md`](eu_sovereignty_charter.md).

---

## Maintenance contract

Update triggers:
- BSI publishes new Bausteine or a new edition
- Operator flags a mapping gap from a concrete audit
- A new codex container is added → document the Baustein mapping
- Major Codex release that changes the security posture

This page is a skeleton — in a concrete audit, the operator fills the
`TODO:` markers with references to specific configuration files and
operational procedures.
