# GDPR DPIA — Template

This page is a **Data Protection Impact Assessment template** under
GDPR Art. 35 for operators deploying MoE Codex. It is structured as a
Markdown form: copy this file into your internal compliance repo, fill
in each section, and have the data-protection officer sign off.

> **Form, not record.** This file in the moe-codex repo is the empty
> template. Filled-in DPIAs live in operator-controlled storage and must
> not be checked into this public repo.

---

## 1. Processing description

- **Name of processing operation:** _<use-case name>_
- **Controller (operator):** _<entity, address>_
- **Data Protection Officer:** _<name, email>_
- **Status / version:** _<YYYY-MM-DD, version>_

### 1.1 Purpose of processing
_<Concrete description — not "AI support" but "preliminary review of
building permit applications", "research on pharmaceutical side effects",
"police situational picture for organised crime", etc.>_

### 1.2 Legal basis
- [ ] Art. 6(1)(a) (consent)
- [ ] Art. 6(1)(b) (contract performance)
- [ ] Art. 6(1)(c) (legal obligation) — _<which?>_
- [ ] Art. 6(1)(e) (public interest) — _<which?>_
- [ ] Art. 6(1)(f) (legitimate interest) — _<attach balancing test>_
- [ ] Art. 9(2) (special categories) — _<which exception?>_

### 1.3 Data subject categories
_<e.g. applicants, patients, suspects, employees; absolute count and
percentage of the relevant German / EU population>_

### 1.4 Data categories
- [ ] Master data (name, address, date of birth)
- [ ] Contact data (email, phone)
- [ ] Contract data
- [ ] Health data (Art. 9 GDPR)
- [ ] Criminal data (Art. 10 GDPR)
- [ ] Biometric data (Art. 9 GDPR)
- [ ] Other special categories — _<which?>_
- [ ] Anonymised / pseudonymised data

---

## 2. Processing operations in MoE Codex

| Step | Component | Personal-data scope |
|---|---|---|
| 2.1 Data ingress | Bundle import via `/v1/codex/approval/import/pending` | Data flow into lakeFS branch (encrypted on MinIO) |
| 2.2 Admin review | `/approval` page | Data visible to admin role (Authentik OIDC, 2FA mandatory) |
| 2.3 Approval decision | `/v1/codex/approval/.../approve` | On click: bundle into Neo4j (moe-sovereign) + lakeFS merge |
| 2.4 Lineage recording | Marquez | Audit trail: who approved what, when |
| 2.5 Drift detection | `services/data_health` | Statistical anomalies — no PII |
| 2.6 Catalog display | `/catalog` | Aggregated metadata only, no raw content |
| 2.7 Investigative search | Cypher explorer (moe-sovereign) | Read-only, RBAC-controlled |
| 2.8 Deletion | `lakefs branch delete` + Neo4j delete script | Operator workflow; codex supplies the tools |

---

## 3. Necessity and proportionality

- **Suitability:** _<Why does MoE Codex solve the concrete problem better
  than alternatives?>_
- **Necessity:** _<Which less-intrusive means were considered? Why do
  Excel, manual review, rule-based filters not suffice?>_
- **Proportionality:** _<Is the burden on data subjects proportional to
  the processing purpose?>_

---

## 4. Risk assessment for data-subject rights

### 4.1 Identified risks

| # | Risk | Likelihood | Severity |
|---|---|---|---|
| 1 | Unauthorised access to bundle contents before approval | _<low/med/high>_ | _<low/med/high>_ |
| 2 | Wrong approval decision leads to wrong entry in the knowledge graph | _<…>_ | _<…>_ |
| 3 | Drift-event logs unexpectedly contain PII | _<…>_ | _<…>_ |
| 4 | Lineage data in Marquez is misused for profiling | _<…>_ | _<…>_ |
| 5 | Sovereignty breach: data leaves the EU | _<…>_ | _<…>_ |
| 6 | _<additional use-case-specific risks>_ | | |

### 4.2 Technical and organisational measures

| Risk | Measure | Where in MoE Codex |
|---|---|---|
| 1 | Authentik OIDC with 2FA, RBAC, markings layer (OPA planned) | `services/auth` in sovereign, `routes/approval` in codex |
| 2 | Two-stage approval workflow (four-eyes principle) — operator configuration | configurable in approval plugin |
| 3 | Drift logs carry aggregate metrics only (compute_drift output) | `services/data_health.compute_drift` |
| 4 | Marquez access restricted to admin role; no PII in lineage events | configurable via OPA policy |
| 5 | EU-host obligation in operator contract; see `eu_sovereignty_charter.md` | platform constraint |

### 4.3 Residual risk

_<If residual risk remains high after all measures: consult the
supervisory authority per Art. 36 GDPR. Otherwise: justify why the
residual risk is acceptable.>_

---

## 5. Contributors and sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Operator (controller) | _<>_ | _<>_ | _<>_ |
| Data protection officer | _<>_ | _<>_ | _<>_ |
| IT security officer | _<>_ | _<>_ | _<>_ |
| Business owner | _<>_ | _<>_ | _<>_ |

---

## 6. Review cycle

- **Initial DPIA:** _<before go-live>_
- **Regular review:** annually or upon material change (Art. 35(11))
- **Ad-hoc review triggers:**
  - New data category added
  - New recipient category (e.g. new tenant, federal state)
  - Serious data-protection incident
  - Material update of MoE Codex (major release)

---

## 7. Cross-reference to AI Act risk-class mapping

If the use case falls under the EU AI Act: additionally complete
[`eu_ai_act_mapping.md`](eu_ai_act_mapping.md) and attach it. The DPIA
under GDPR is structurally compatible with the risk assessment under
AIA Art. 9 — we recommend a single combined document.

---

*This template reflects the state of the art as of 2026-05; it does not
replace legal advice. Operators consult their own compliance function
and, where applicable, the competent supervisory authority.*
