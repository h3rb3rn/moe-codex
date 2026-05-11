---
title: <Use-Case-Name>
industry: <Branche>
maturity: experimental  # experimental | beta | production
ai_act_risk: limited    # minimal | limited | high | unacceptable
required_modules:
  - graph_rag           # always required
  # - mcp_tools
  # - codex_catalog
  # - codex_approval
  # - codex_lineage
  # - codex_versioning
  # - codex_notebook
  # - codex_nifi
required_experts:
  - general_assistant   # replace with relevant expert IDs
recommended_models:
  planner: ""           # empty = use moe-sovereign routing
  judge: ""
gdpr_relevance: none    # none | personal_data | special_category
bsi_baustein: []        # e.g. [APP.2.1, NET.1.1]
nis2_sector: []         # e.g. [energy, healthcare]
---

# <Use-Case-Name>

## Problem

> Describe the business or operational problem this use case solves. 2–4 sentences.
> Who is affected? What happens without this solution?

## Architecture

```mermaid
flowchart LR
    A[Data Source] --> B[moe-sovereign\nGraphRAG + Routing]
    B --> C[moe-codex\nCatalog / Lineage]
    C --> D[Regulated Operator\nApproval / Audit]
```

## Data Flow

| Step | Input | Transform | Output |
|------|-------|-----------|--------|
| 1    |       |           |        |
| 2    |       |           |        |

## Expert Routing

Describe which expert categories handle which sub-tasks and why.

## Example Prompts

```
# Prompt 1 — <intent>
<prompt text>
```

```
# Prompt 2 — <intent>
<prompt text>
```

## Prometheus KPIs

| Metric | Threshold | Alert |
|--------|-----------|-------|
| `moe_request_duration_seconds` | p95 < 5s | page oncall |

## Compliance Checklist

- [ ] GDPR Art. 5 (purpose limitation) verified
- [ ] AI Act risk class documented
- [ ] Audit trail enabled (Marquez lineage)
- [ ] Data retention policy configured
- [ ] Access control (OPA policy or Authentik group) in place
