# EU AI Act — Risk-Class Mapping

This page maps **MoE Codex use-cases** to the risk classes defined in the
EU AI Act (Verordnung 2024/1689, in Kraft seit 01.08.2024) and the
operator obligations that follow per class.

> **Operator perspective.** The risk class is determined by *how the
> operator uses* the platform, not by the platform itself. MoE Codex is a
> general-purpose data and audit layer; it can be used in zero-risk (no
> AI), limited-risk, and high-risk scenarios. This page is the operator's
> checklist, not a compliance certificate.

---

## 1. Risk-class ladder (Art. 6 ff.)

| Class | Description (German) | Examples in our context |
|---|---|---|
| **Unzulässig** (Art. 5) | Verbotene Praktiken: Social Scoring, biometrische Live-Erkennung im öffentlichen Raum, Manipulation, Schwachstellen-Ausnutzung | **Nicht erlaubt.** MoE Codex darf nicht für diese Zwecke deployt werden. |
| **Hochrisiko** (Art. 6 + Anhang III) | Bewerbungs-/Beförderungs-/Personalentscheidung, Justiz/Polizei, KritIS (Wasser/Strom/Verkehr), Bildung, Migrationsbehörde, soziale Leistungen | Strafverfolgung-Investigations-Workflow, Polizei-Lagebild, KritIS-Compliance-Audit, behördliche Asyl-/Sozialfall-Bearbeitung |
| **Begrenzt** (Art. 50) | KI-Interaktion mit natürlichen Personen, Emotions-/Biometrie-Klassifikation, Deepfake-Generierung | Chatbot-Interface über moe-sovereign, Knowledge-Bundle-Approval mit Personen-Eintrag |
| **Minimal** | Alles andere | Datenkatalog ohne PII, Lineage über technische Datasets, ETL-Pipeline für interne Forschungs-Datensätze |

---

## 2. Operator-Pflichten je Klasse

### Bei Hochrisiko (Anhang III)

| Pflicht | Wo in moe-codex unterstützt? |
|---|---|
| **Risk Management System** (Art. 9) | `/v1/codex/health/events` für Drift-Detection; Catalog für Datenherkunfts-Audit |
| **Data Governance** (Art. 10) | lakeFS-Branching, Marquez-Lineage, Approval-Gate vor jedem Schreibzugriff |
| **Technical Documentation** (Art. 11 + Anhang IV) | dieses Repo (`docs/`), `palantir_comparison.md`, OpenAPI-Schemata in `docs/api/` |
| **Record-Keeping (Logging)** (Art. 12) | Marquez-Run-Events, Drift-Events in Redis (cap 500), Audit-Trail per lakeFS-Commit |
| **Transparency Obligations** (Art. 13) | Admin-UI zeigt Quellen pro Catalog-Eintrag; Approval-Workflow macht Bundles vor Schreibzugriff sichtbar |
| **Human Oversight** (Art. 14) | Approval-Workflow per Definition: kein automatischer Import in Neo4j ohne Admin-Klick |
| **Accuracy, Robustness, Cybersecurity** (Art. 15) | Drift-Detection-Severity-Ladder, lakeFS-Branch-Rollback, OPA-Policy-Layer (Phase D.1.1) |
| **Conformity Assessment** (Art. 43) | Operator-Pflicht — wir liefern die `dsgvo_dpia_template.md` und `bsi_grundschutz_mapping.md` als Belege |
| **CE-Marking + EU-Datenbank-Eintrag** | Operator-Pflicht — kein Plattform-Support |

### Bei Begrenzt (Art. 50)

| Pflicht | Wo unterstützt? |
|---|---|
| Nutzer informieren, dass sie mit KI interagieren | Über moe-sovereign Chat-UI; Codex selbst hat keine Nutzer-Interaktion |
| Deepfake-Markierung | nicht relevant — Codex generiert keine Medien |
| Emotion-/Biometrie-Hinweis | nicht relevant |

### Bei Minimal

Keine Pflicht; freiwillig DPIA empfohlen.

---

## 3. Open-Source-Privileg (Art. 2 Abs. 12)

MoE Codex ist **Free and Open Source AI** (Apache 2.0). Damit greift das
Open-Source-Privileg nach Art. 2 Abs. 12:

> "Diese Verordnung gilt nicht für KI-Systeme, die als freie und
> Open-Source-Software freigegeben werden, es sei denn, sie werden als
> Hochrisiko-KI-Systeme oder als KI-Systeme, die unter Art. 5 oder Art. 50
> fallen, in Verkehr gebracht oder in Betrieb genommen."

**Konsequenz:**
- Wer Codex herunterlädt und für Minimal-/Begrenzt-Risiko-Zwecke einsetzt:
  reduzierte Pflichten (im Wesentlichen Art. 50 wo zutreffend).
- Wer Codex für **Hochrisiko-Zwecke** einsetzt (z.B. behördliche
  Investigations-Plattform): **volle Pflichten** wie oben.

Wir empfehlen, vor Inbetriebnahme eine schriftliche Risikoklassifizierung
für den konkreten Use Case zu erstellen. Template:
`docs/system/dsgvo_dpia_template.md` (DPIA-Vorlage gemäß Art. 35 DSGVO,
strukturell kompatibel mit Art. 9 AIA Risk Management).

---

## 4. GPAI-Modelle (Art. 51 ff.)

Die LLMs, die `moe-sovereign` orchestriert (Mistral, Llama, Qwen,
Mathstral), sind **General Purpose AI Models** im Sinne von Art. 51 AIA.

| Pflicht | Erfüllt durch |
|---|---|
| Modell-Dokumentation | Hugging Face Model Cards der jeweiligen Anbieter |
| Trainings-Daten-Transparenz | Anbieter-Veröffentlichungen (Mistral, Meta, Alibaba) |
| Urheberrechts-Compliance | Anbieter-Erklärung; Operator prüft im Einkaufsprozess |
| Cybersecurity | Aktuelle Modell-Versionen; Operator pinnt Versionen via `ollama pull` |

GPAI-Pflichten gelten beim **Anbieter** des Modells, nicht beim Operator
oder bei der Plattform. Operator nimmt die Anbieter-Dokumentation zur
Kenntnis und legt sie der Conformity-Assessment-Akte bei.

---

## 5. Zeitleiste (für Operator-Planung)

| Datum | Stufe |
|---|---|
| 01.08.2024 | EU AI Act in Kraft |
| 02.02.2025 | Verbotene Praktiken (Art. 5) anwendbar; KI-Kompetenz-Pflicht (Art. 4) |
| 02.08.2025 | GPAI-Pflichten (Art. 51 ff.) anwendbar; Governance/Sanktionen aktiv |
| 02.08.2026 | Anhang-III-Hochrisiko-System-Pflichten anwendbar |
| 02.08.2027 | Restliche Hochrisiko-Pflichten (Art. 6 Abs. 1) anwendbar |

Konsequenz: Wer 2025-2026 einen Hochrisiko-Anwendungsfall startet, muss
spätestens **02.08.2026** voll konform sein. MoE Codex unterstützt das
operativ über alle hier genannten Module — die Conformity-Assessment-Akte
selbst bleibt Operator-Pflicht.

---

## 6. Maintenance contract

Update triggers für diese Page:
- Beratungspraxis publiziert offizielles AIA-Guidance-Dokument
- Operator meldet einen neuen Use-Case und braucht Risk-Class-Beurteilung
- Anhang III wird erweitert (Delegated Acts der Kommission)
- Standards-Veröffentlichungen aus CEN-CENELEC zu KI-Konformität

Diese Page ist **nicht** rechtsverbindlich. Operator konsultiert eigene
Compliance-Abteilung für die finale Risk-Class-Beurteilung.
