# Use Cases

MoE Codex is designed for regulated industries where data sovereignty, full audit trails, and compliance-ready provenance are non-negotiable. Each use case documents the architecture, data flow, expert routing, and specific compliance requirements for one industry context.

## Maturity Levels

| Badge | Meaning |
|-------|---------|
| **production** | Fully documented, tested, reference deployment available |
| **beta** | Architecture validated, compliance checklist defined, awaiting production hardening |
| **experimental** | Architecture concept only — requires customisation and independent legal/security review |

## Use Case Index

| Industry | File | Maturity | AI Act Risk |
|----------|------|----------|-------------|
| Pharma & Life Sciences | [pharma.md](scenarios/pharma.md) | production | high |
| Academic & Scientific Research | [research.md](scenarios/research.md) | production | minimal |
| Healthcare & Hospital Networks | [healthcare.md](scenarios/healthcare.md) | beta | high |
| Government & Public Sector | [government.md](scenarios/government.md) | beta | high |
| Banking & Finance | [banking.md](scenarios/banking.md) | beta | high |
| Energy & Utilities | [energy.md](scenarios/energy.md) | beta | high |
| Manufacturing & Industry 4.0 | [manufacturing.md](scenarios/manufacturing.md) | beta | limited |
| Logistics & Supply Chain | [supply_chain.md](scenarios/supply_chain.md) | beta | limited |
| Cybersecurity & SOC | [cybersecurity.md](scenarios/cybersecurity.md) | beta | limited |
| Telecommunications | [telco.md](scenarios/telco.md) | beta | limited |
| Civil Protection & Crisis Management | [crisis_response.md](scenarios/crisis_response.md) | beta | high |
| Insurance | [insurance.md](scenarios/insurance.md) | experimental | high |
| Defence & Public Security | [defense.md](scenarios/defense.md) | experimental | unacceptable |

## Starting a New Use Case

Copy `_template.md`, fill in the frontmatter, and follow the section structure. A use case is ready for `beta` status when:

1. Architecture diagram is complete
2. Data flow table covers all pipeline stages
3. Expert routing rationale is documented
4. Compliance checklist is populated with relevant regulations
