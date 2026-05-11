# Use-Case Discovery

Before deploying MoE Codex, you need a clear answer to: *which problem are we solving, for whom, with what data, and under which legal constraints?* This page gives you a repeatable method.

## Discovery Workshop Agenda (Half-Day)

**Participants:** Domain expert, data engineer, compliance/legal representative, IT security.

| Time | Activity | Output |
|------|----------|--------|
| 0:00–0:30 | Problem framing: what decision is currently made manually or poorly? | Problem statement (2 sentences) |
| 0:30–1:00 | Data inventory: what datasets exist, where do they live, who owns them? | Data source table |
| 1:00–1:30 | Regulatory scan: which laws apply? (GDPR, AI Act, sector-specific) | Compliance checklist draft |
| 1:30–2:00 | Module selection: which Codex modules are needed? | Required modules list |
| 2:00–2:30 | Success criteria: how will you know it works? | KPIs + acceptance criteria |
| 2:30–3:00 | Risk assessment: what could go wrong, what is the rollback plan? | Risk register |

## Module Selection Decision Tree

```
Does the use case involve regulated data (health, finance, citizen data)?
  YES → codex_approval (mandatory)
  NO  → codex_approval optional (for internal governance)

Does the use case require full audit trail for regulators or auditors?
  YES → codex_lineage (mandatory)
  NO  → codex_lineage optional (for internal traceability)

Does the use case involve multiple dataset versions or branching analysis?
  YES → codex_versioning (mandatory)
  NO  → codex_versioning optional

Does the use case need free-form data analysis or exploratory queries?
  YES → codex_notebook

Does the use case ingest from external or heterogeneous data sources?
  YES → codex_nifi
```

## Interview Templates

### For domain experts

1. What is the most time-consuming manual step in your current workflow?
2. Which data sources would you need to combine to answer your most important question?
3. Who reviews and approves your outputs before they are acted on?
4. What would happen if the system gave a wrong answer? (Risk calibration)

### For data engineers

1. Where does the raw data live? Format, volume, update frequency?
2. Are there existing ETL pipelines? Which tools?
3. What are the data quality issues we should expect?
4. What are the network / firewall constraints for data movement?

### For compliance / legal

1. Which data categories are involved? (Personal, special category, confidential)
2. Is there a legal basis for automated processing? (Art. 6/9 GDPR, sector law)
3. Is an AI Act risk assessment required? (Annex III categories)
4. What does the audit trail need to show for regulatory examinations?

## Routing Architecture Choices

| Scenario | Recommended routing | Reason |
|----------|--------------------|----|
| Single domain, one expert | Direct routing via expert template | No overhead |
| Multi-domain query (e.g. clinical + legal) | Planner + judge pattern | Planner decomposes, judge reconciles |
| High-risk AI decision (AI Act) | Planner + human approval gate | Mandatory human-in-the-loop |
| Exploratory / notebook | Direct to `research_assistant` or `data_analyst` | No approval needed for exploration |
