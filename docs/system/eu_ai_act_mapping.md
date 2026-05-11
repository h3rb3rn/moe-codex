# EU AI Act — Risk-Class Mapping

This page maps **MoE Codex use cases** to the risk classes defined in the
EU AI Act (Regulation 2024/1689, in force since 2024-08-01) and the
operator obligations that follow per class.

> **Operator perspective.** The risk class is determined by *how the
> operator uses* the platform, not by the platform itself. MoE Codex is a
> general-purpose data and audit layer; it can be used in zero-risk (no
> AI), limited-risk, and high-risk scenarios. This page is the operator's
> checklist, not a compliance certificate.

---

## 1. Risk-class ladder (Art. 6 ff.)

| Class | Description | Examples in our context |
|---|---|---|
| **Prohibited** (Art. 5) | Forbidden practices: social scoring, real-time biometric identification in public spaces, manipulation, exploitation of vulnerabilities | **Not permitted.** MoE Codex must not be deployed for these purposes. |
| **High-risk** (Art. 6 + Annex III) | Recruitment / promotion / employment decisions, justice and law enforcement, critical infrastructure (water/electricity/transport), education, migration authorities, social benefits | Law-enforcement investigation workflow, police situational picture, KritIS compliance audit, public-authority asylum or social case handling |
| **Limited** (Art. 50) | AI interaction with natural persons, emotion/biometric classification, deepfake generation | Chatbot interface via moe-sovereign, knowledge-bundle approval that lists named persons |
| **Minimal** | Everything else | Data catalog without PII, lineage over technical datasets, ETL pipeline for internal research datasets |

---

## 2. Operator obligations per class

### When high-risk (Annex III)

| Obligation | How MoE Codex supports it |
|---|---|
| **Risk management system** (Art. 9) | `/v1/codex/health/events` for drift detection; catalog for data-provenance audit |
| **Data governance** (Art. 10) | lakeFS branching, Marquez lineage, approval gate before every write |
| **Technical documentation** (Art. 11 + Annex IV) | this repo (`docs/`), `palantir_comparison.md`, OpenAPI schemas in `docs/api/` |
| **Record-keeping (logging)** (Art. 12) | Marquez run events, drift events in Redis (cap 500), audit trail via lakeFS commits |
| **Transparency** (Art. 13) | Admin UI shows source per catalog row; approval workflow surfaces bundles before any write |
| **Human oversight** (Art. 14) | Approval workflow by design: no automatic import into Neo4j without an admin click |
| **Accuracy, robustness, cybersecurity** (Art. 15) | Drift-detection severity ladder, lakeFS branch rollback, OPA policy layer (planned) |
| **Conformity assessment** (Art. 43) | Operator obligation — we supply `dsgvo_dpia_template.md` and `bsi_grundschutz_mapping.md` as evidence |
| **CE marking + EU database registration** | Operator obligation — no platform support |

### When limited (Art. 50)

| Obligation | How supported |
|---|---|
| Inform users that they are interacting with AI | Handled by moe-sovereign chat UI; codex itself has no end-user interaction |
| Deepfake labelling | Not relevant — codex generates no media |
| Emotion/biometric disclosure | Not relevant |

### When minimal

No obligations; voluntary DPIA recommended.

---

## 3. Open-source privilege (Art. 2(12))

MoE Codex is **free and open-source AI** (Apache 2.0). The open-source
privilege under Art. 2(12) applies:

> "This Regulation does not apply to AI systems released under free and
> open-source licences, unless they are placed on the market or put into
> service as high-risk AI systems or as AI systems that fall under
> Articles 5 or 50."

**Consequence:**
- Operators deploying codex for minimal- or limited-risk purposes have
  reduced obligations (essentially Art. 50 where applicable).
- Operators deploying codex for **high-risk purposes** (e.g. a
  public-authority investigation platform) carry **full obligations** as
  listed above.

We recommend producing a written risk classification for the concrete use
case before going live. Template:
[`docs/system/dsgvo_dpia_template.md`](dsgvo_dpia_template.md) (DPIA form
under GDPR Art. 35, structurally compatible with AIA Art. 9 risk
management).

---

## 4. GPAI models (Art. 51 ff.)

The LLMs that `moe-sovereign` orchestrates (Mistral, Llama, Qwen,
Mathstral) are **general-purpose AI models** within the meaning of
Art. 51 AIA.

| Obligation | Satisfied by |
|---|---|
| Model documentation | Hugging Face Model Cards published by each provider |
| Training-data transparency | Provider disclosures (Mistral, Meta, Alibaba) |
| Copyright compliance | Provider statement; operator verifies during procurement |
| Cybersecurity | Recent model versions; operator pins versions via `ollama pull` |

GPAI obligations rest with the **model provider**, not the operator or
the platform. The operator acknowledges provider documentation and files
it with the conformity-assessment record.

---

## 5. Timeline (for operator planning)

| Date | Stage |
|---|---|
| 2024-08-01 | EU AI Act enters into force |
| 2025-02-02 | Prohibited practices (Art. 5) applicable; AI-literacy duty (Art. 4) |
| 2025-08-02 | GPAI obligations (Art. 51 ff.) applicable; governance and sanctions active |
| 2026-08-02 | Annex III high-risk system obligations applicable |
| 2027-08-02 | Remaining high-risk obligations (Art. 6(1)) applicable |

Consequence: any operator launching a high-risk use case in 2025-2026
must be fully conformant by **2026-08-02**. MoE Codex supports this
operationally across all modules listed above — the conformity-assessment
record itself remains the operator's responsibility.

---

## 6. Maintenance contract

Update triggers:
- Regulators publish official AIA guidance documents
- An operator flags a new use case requiring risk-class assessment
- Annex III is amended (delegated acts of the Commission)
- CEN-CENELEC publishes harmonised AI conformity standards

This page is **not legally binding**. Operators consult their own
compliance function for the final risk-class determination.
