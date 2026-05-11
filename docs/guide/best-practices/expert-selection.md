# Expert Selection

MoE Sovereign routes queries to specialised expert LLM configurations via deterministic template matching. This page helps you pick the right experts for your MoE Codex use case and configure the routing in the Admin UI.

## Expert Category Overview

MoE Sovereign provides 15 expert categories. The table below maps each to the Codex use cases it covers best.

| Expert ID | Domain | Best for |
|-----------|--------|----------|
| `general_assistant` | General | Cross-domain summaries, onboarding queries, initial triage |
| `medical_consult` | Healthcare / Pharma | Clinical interpretation, adverse events, biomarker analysis |
| `legal_advisor` | Legal / Compliance | Regulatory text, GDPR analysis, submission language, SOP review |
| `financial_advisor` | Banking / Finance / Insurance | Risk model explanations, regulatory gap analysis, audit prep |
| `research_assistant` | Academic / R&D | Literature synthesis, hypothesis generation, methodology review |
| `data_analyst` | Cross-domain analytics | Statistical analysis, correlation, visualisation code |
| `technical_expert` | Engineering / IT / OT | Root cause analysis, system diagnosis, architecture review |
| `security_expert` | Cybersecurity / SOC | Threat analysis, CVE triage, incident investigation |
| `code_reviewer` | Software development | Code review, refactoring suggestions |
| `document_processor` | Document intelligence | OCR output cleaning, table extraction, form parsing |
| `translator` | Multilingual | Regulatory document translation, cross-language search |
| `summariser` | Long-form content | Meeting notes, report summaries, RFP digests |

## Routing Configuration

Configure expert routing in the **Admin UI → Configuration → Expert Templates**.

### Single-expert pattern (most use cases)

Set the primary expert to the domain specialist. Example for pharma:

```
Primary expert:  medical_consult
Judge / fallback: legal_advisor  (when query contains "regulation|submission|§|Art.")
```

### Multi-expert / planner pattern (complex cross-domain queries)

Use the planner model to decompose the query, then route sub-tasks to specialists:

```
Planner model:   <your strongest available model>
Expert pool:     [medical_consult, legal_advisor, data_analyst]
Judge model:     <second strongest model>
Merge strategy:  weighted (medical_consult weight: 0.6, legal: 0.3, data: 0.1)
```

### Escalation rules

Define escalation triggers in the template's routing rules:

| Trigger phrase | Escalate to |
|---------------|------------|
| "GDPR", "DSGVO", "Art. 9", "consent" | `legal_advisor` |
| "risk model", "SREP", "BaFin", "Solvency" | `financial_advisor` |
| "adverse event", "IND", "NDA", "EMA" | `medical_consult` |
| "CVE-", "IOC", "MITRE ATT&CK" | `security_expert` |

## Mapping Use Cases to Expert Combinations

| Use Case | Primary | Secondary / Judge |
|----------|---------|------------------|
| Pharma clinical | `medical_consult` | `legal_advisor` |
| Research | `research_assistant` | `data_analyst` |
| Banking risk | `financial_advisor` | `legal_advisor` |
| Government | `legal_advisor` | `general_assistant` |
| Cybersecurity SOC | `security_expert` | `technical_expert` |
| Energy / Manufacturing | `technical_expert` | `data_analyst` |
| Supply Chain ESG | `legal_advisor` | `data_analyst` |
| Crisis Response | `general_assistant` | `technical_expert` |

## Selecting Models for Each Expert

MoE Sovereign allows assigning different model backends per expert. For regulated use cases:

- **High-risk AI Act** categories: assign your highest-quality model as the primary expert and as the judge. Accuracy trumps latency.
- **Exploratory / notebook** queries: a smaller, faster model is appropriate.
- **Air-gapped deployments**: all models must be locally hosted (Ollama on inference nodes). No external API calls.

Configure model assignments in **Admin UI → Configuration → Inference Nodes → Expert Assignment**.
