# NIS2 Readiness — MoE Codex

Skeleton mapping for the NIS2-Umsetzungsgesetz (NIS2UmsuCG, German
transposition of NIS2, status 2024-2025). Addresses "essential" and
"important" entities under § 8 NIS2UmsuCG.

> **Status:** skeleton. Detailed risk-measure tables will be expanded
> once MoE Codex is deployed at a first NIS2-affected operator (e.g. a
> KRITIS operator).

---

## 1. Sectoral applicability

NIS2 covers these sectors (Annex I / II):
- Energy, transport, banking and financial markets, health, drinking
  water, waste water, digital infrastructure, ICT-service management for
  public administration, space, postal services, waste management,
  chemicals, food production, manufacturing of medical devices, critical
  manufacturing subsectors, digital services, research.

If the operator is active in one of these sectors AND meets the size
threshold (typically ≥ 50 staff / ≥ EUR 10 m turnover; KRITIS operators
regardless of size): NIS2 applies.

---

## 2. Requirements mapping

### § 30 NIS2UmsuCG — Risk-management measures

| Requirement | Satisfied by |
|---|---|
| (1) Risk-analysis concept + information-security policy | TODO — operator obligation; codex supplies building blocks |
| (2) Handling of security incidents | Drift events + Kafka audit trail + Falco (planned) |
| (3) Business continuity (backup / restore) | `scripts/migrate-from-sovereign.sh` as a template |
| (4) Supply-chain security | `audit-licenses.sh` + `license_compliance.md` |
| (5) Security in acquisition, development, maintenance | Apache-2.0 source transparency |
| (6) Effectiveness review | `pytest` suite + drift detection as ongoing effectiveness check |
| (7) Basic cyber hygiene + training | Operator obligation |
| (8) Cryptography | TLS via Caddy; Authentik sessions; lakeFS encryption |
| (9) Personnel security + access control + asset management | Authentik + OPA (planned) |
| (10) Multi-factor auth + emergency communication | Authentik 2FA |

### § 32 NIS2UmsuCG — Reporting obligations

| Deadline | Duty | Codex support |
|---|---|---|
| 24 h | Early warning to BSI | Alerting path: drift event `severity: crit` → Falco alert → SIEM |
| 72 h | Full report | Marquez events + drift events provide forensics |
| 1 month | Final report | Audit trail via lakeFS commit history |

---

## 3. Maintenance contract

Update triggers:
- BSI publishes NIS2 implementation guidance
- New cybersecurity standards (e.g. ISO 27001:202X revision)
- Operator flags a concrete audit requirement
- Codex extends with audit-relevant components (e.g. OPA policy engine)

This page is a skeleton — the `TODO:` markers will be systematically
filled in during the phase 2 extension work.
